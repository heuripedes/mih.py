# vim: ts=8 sts=4 sw=4 et nu

import os
import collections
import errno
import shlex
import subprocess as subproc
import re
import util
import time

import sockios
sockios.init()

# ModemManager
import mm

# Interface properties

# Wired
WIRED_UP_STRENGHT   = 1000
WIRED_DOWN_STRENGHT = 0

# Wifi
WIFI_ESSID = 'GREDES_TELEMATICA'
WIFI_KEY   = ''
WIFI_THRESHOLD = 37
WIFI_SAMPLES   = 10

# Mobile
MOBILE_GSM_NUMBER = '*99#'
MOBILE_GSM_APN  = 'gprs.oi.com.br'
MOBILE_GSM_USER = 'oi'
MOBILE_GSM_PASS = 'oi'

def get_local_ifnames():
    """
    Looks for links in /proc/net/dev
    """

    # Local common interfaces pci/amr/virtual/etc
    prefixes = ('lo', 'virbr', 'vboxnet', 'ppp0')
    ifnames  = filter(lambda name: not name.startswith(prefixes), sockios.get_iflist())
    ifnames += mm.ModemManager.EnumerateDevices()

    return ifnames

#def get_modems():
#    modems = mm.ModemManager.EnumerateDevices()
#    for m in modems:
#        print m + ":"
#        
#        import pprint
#        link = make_link(ifname=m)
#        link.up()
#        pprint.pprint(link.as_dict())
#        link.down()
#        os.abort()
#
#    return modems

def make_link(**kwargs):
    if kwargs.get('remote', False):
        if kwargs.get('wired'):
            return Link80203(**kwargs)
        elif kwargs.get('wifi'):
            return Link80211(**kwargs)
        elif kwargs.get('mobile'):
            return LinkMobile(**kwargs)
   
    ifname = kwargs.get('ifname')
    if ifname.startswith('/'):
        return LinkMobile(**kwargs)
    elif os.path.isdir('/sys/class/net/'+ifname+'/wireless'):
        return Link80211(**kwargs)
    else:
        return Link80203(**kwargs)


class Link(object):

    def __init__(self, **kwargs):
        
        # Callbacks
        self.on_link_event = None

        self.state = None # force link_up on first poll()
        self.ipaddr = ''
        self.discoverable = True

        self.update(**kwargs)
        #self.poll()


    @property
    def wifi(self):
        return self.technology == 'wifi'


    @property
    def mobile(self):
        return self.technology == 'mobile'


    @property
    def wired(self):
        return self.technology == 'wired'

    
    def __repr__(self):
        return '%s(name=%s, ipv4=%s)' %\
                (self.__class__.__name__, self.ifname, self.__dict__.get('ipaddr'))


    def update(self, *args, **kwargs):
        if not kwargs:
            kwargs = args[0]
            
        #self.wifi, self.wired, self.mobile = False, False, False
        
        if not hasattr(self, 'remote'):
            self.remote = kwargs.pop('remote', False)

        if not hasattr(self, 'name'):
            self.name   = kwargs.pop('name', None)

        if not hasattr(self, 'ifname'):
            self.ifname =  kwargs.pop('ifname') # for now, required.

        if self.remote: 
            self._ready = kwargs.pop('ready', False)

            # Remote link information is mostly static
            #self.macaddr = kwargs.pop('macaddr', None)
            self.ipaddr  = kwargs.pop('ipaddr', None)
            self.state    =  kwargs.pop('state', False)

        else:
            self._poll_ifconf()

    
    def _poll_ifconf(self):
        ifconf = sockios.get_ifconf(self.ifname);
        self.macaddr = ifconf['hw_addr']
        self.ipaddr  = ifconf['in_addr']


    def poll(self):
        if self.remote:
            return

        self._poll_ifconf()

        self.state = sockios.is_up(self.ifname) and self.ipaddr


    def poll_and_notify(self):
        if self.remote:
            return

        before = self.is_ready()

        self.poll()

        is_ready = self.is_ready()

        if before != is_ready:
            if is_ready and self.on_link_event:
                self.on_link_event(self, 'up')

            if not is_ready and self.on_link_event:
                self.on_link_event(self, 'down')
   

    def up(self):
        assert not self.remote

        if self.is_ready():
            return True

        sockios.set_up(self.ifname)

        self.poll()

        return self.state

    
    def down(self):
        assert not self.remote

        # This link is already down, nothing to do here.
        if not self.state:
            return True

        util.dhcp_release(self.ifname)

        cmd = shlex.split('ip addr flush dev '+self.ifname)
        success = (subproc.call(cmd) == 0)

        cmd = shlex.split('ip link set down dev '+self.ifname)
        success = (subproc.call(cmd) == 0)

        self.poll()

        if success and not self.is_ready() and self.on_link_event:
            self.on_link_event(self, 'down')
        
        return success


    def is_ready(self):
        return (getattr(self, '_ready', False) or
                (self.state and self.ipaddr is not None))


    def as_dict(self):
        d = self.__dict__.copy()

        if self.remote and hasattr(d, '_ready'):
            d['ready'] = d['_ready']
            del d['_ready']

        del d['on_link_event']

        return d


class Link80203(Link):

    def __init__(self, **kwargs):
        self.technology = 'wired'

        super(Link80203, self).__init__(**kwargs)


    def update(self, *args, **kwargs):
        super(Link80203, self).update(*args, **kwargs)

        #if self.remote:
        #    self.carrier = kwargs.pop('carrier', False)


    def poll(self):

        super(Link80203, self).poll()

        if self.state:
            # XXX: is the carrier information really needed?
            ## XXX: one exception might originate here if the interface
            ##      goes down before the read completes.
            #with open('/sys/class/net/'+self.ifname+'/carrier') as f:
            #    self.carrier = f.readline().strip() == '1'
            
            self.strenght = WIRED_UP_STRENGHT
        else:
            self.strenght = WIRED_DOWN_STRENGHT


    def up(self):
        super(Link80203, self).up()

        if self.is_ready():
            return True

        if not super(Link80203, self).up():
            return False

        util.dhcp_release(self.ifname)
        success = util.dhcp_renew(self.ifname)
            
        self.poll()

        if self.is_ready() and self.on_link_event:
            self.on_link_event(self, 'up')
        
        return success and self.is_ready()


class Link80211(Link):
    def __init__(self, **kwargs):
        self.technology = 'wifi'

        super(Link80211, self).__init__(**kwargs)


    def update(self, *args, **kwargs):
        super(Link80211, self).update(*args, **kwargs)

        # Reset sampling 
        self.strenght = 0
        self.samples  = collections.deque(maxlen=WIFI_SAMPLES)

        if self.remote:
            self.strenght =  kwargs.pop('strenght', -1)


    def poll(self):
        super(Link80211, self).poll()

        # Collect signal strenght samples
        if not self.is_ready():
            self.strenght = 0
            self.samples.clear()
            self.essid = None
        else:
            with open('/sys/class/net/'+self.ifname+'/wireless/link') as f:
                self.strenght = int(f.readline().strip())
                self.samples.append(self.strenght)

            matches = util.match_output('ESSID:"([^"$]+)', 'iwconfig '+ self.ifname)
            self.essid = matches[0].strip()
   

    def poll_and_notify(self):
        super(Link80211, self).poll_and_notify()

        if not self.is_ready():
            return
        
        if self.is_going_down():
            if self.on_link_event:
                self.on_link_event(self, 'going down')


    def up(self):
        assert not self.remote

        if self.is_ready():
            return True

        subproc.call(['rfkill', 'unblock', 'all'])

        if not super(Link80211, self).up():
            return False

        essid = WIFI_ESSID
        key   = WIFI_KEY

        cmd = ['iwconfig', self.ifname, 'essid', essid]

        if key:
            cmd.append('key')
            cmd.append(key)

        success = subproc.call(cmd) == 0
        
        util.dhcp_release(self.ifname)
        success = success and util.dhcp_renew(self.ifname)
            
        self.poll()

        success = success and self.is_ready()

        if success and self.on_link_event:
            self.on_link_event(self, 'up')
        
        return success

    def is_going_down(self):
        return (self.wifi and len(self.samples) == WIFI_SAMPLES and
                util.average(self.samples) < WIFI_THRESHOLD)


# XXX: based on https://github.com/openshine/ModemManager/blob/master/test/mm-test.py
class LinkMobile(Link):

    def __init__(self, **kwargs):

        self.discoverable = False

        self.technology = 'mobile'

        if not kwargs.get('remote'):

            self._modem = mm.Modem(kwargs.get('ifname'))

            if self._modem.Type != mm.MM_MODEM_TYPE_GSM:
                raise 'Unsupported modem type.'

            self._dbus_name = kwargs.get('ifname')

            self.m_master = self._modem.MasterDevice
            self.m_device = self._modem.Device

            kwargs['ifname'] = None

        super(LinkMobile, self).__init__(**kwargs)


    def update(self, *args, **kwargs):
        super(LinkMobile, self).update(*args, **kwargs)
        
        self.ipaddr = None
        self.strenght = 0
        self.samples  = collections.deque(maxlen=WIFI_SAMPLES)

        if self.remote:
            self.strenght =  kwargs.pop('strenght', -1)
 

    def _poll_ifconf(self):
        if self.ifname:
            super(LinkMobile, self)._poll_ifconf()


    def poll(self):
        if self.remote:
            return
        
        self.state = (self._modem.State == mm.MM_MODEM_STATE_CONNECTED)
        if not state:
            return
        
        status = self._modem.GetStatus()

        if not self.is_ready():
            self.strenght = 0
            self.samples.clear()
        else:
            self.strenght = status['signal-quality']
            self.samples.append(self.strenght)

        super(LinkMobile, self).poll()


    def poll_and_notify(self):
        super(LinkMobile, self).poll_and_notify()

  
    def _enable(self, enable):
        if enable:
            print 'Enabling modem...'
        else:
            print 'Disabling modem...'

        try:
            self._modem.Enable(enable)
            return True
        except dbus.DBusException, e:
            if enable:
                print 'Failed to enable the modem: %s' % e
            else:
                print 'Failed to disable the modem: %s' % e

            return False
    
    
    def _pppd_connect(self): # osi data link layer (ppp)
        args = [
                '/usr/sbin/pppd',  # command
                'nodetach', 'lock', 'nodefaultroute', 'noipdefault',
                'noauth', 'crtscts', 'modem', 'usepeerdns', 
                #'debug',
                '115200' # baud
                ]

        if MOBILE_GSM_USER:
            args += ['user', MOBILE_GSM_USER]
        
        args += [self.m_device]

        #print 'Running pppd...'

        try:
            # XXX: pppd output must be unbufered or read()/write() will block.
            # in case pppd stdout is buffered, use UNIX sockets using socket.socketpair()
            self._pppd = subproc.Popen(args, cwd='/', env={},
                    stdout=subproc.PIPE, stderr=subproc.PIPE)
        except IOError, e:
            print 'Failed to run pppd: %s' % e
            return False
     
        # non-blockign stdout
        util.set_blocking(self._pppd.stdout.fileno(), False)
        
        attempts = 200 # 20 secs
        while (self._pppd.poll() is None and 
                (not self.ifname or not self.ipaddr) and
                attempts):
            line = None
            try:
                line = self._pppd.stdout.readline().strip()
            except IOError, e:
                if e.errno == errno.EAGAIN:
                    time.sleep(0.1)
                    attempts -= 1
                    continue
                raise e

            if not line:
                continue

            if not self.ifname:
                matches = re.findall('Using\s+interface\s+([a-z0-9]+)', line)
                if matches:
                    self.ifname = matches[0]
            elif not self.ipaddr:
                matches = re.findall('local\s+IP\s+address\s+([0-9.]+)', line)
                if matches:
                    self.ipaddr = matches[0]
            #print 'attempt:', 200 - attempts,'line:',line
      
        if not self.ifname or not self.ipaddr:
            return False

        return True


    def _connect(self):
        """Register the device with a network provider."""

        print 'Connecting modem...'

        opts = {
                'number':   MOBILE_GSM_NUMBER,
                'apn':      MOBILE_GSM_APN,
                'username': MOBILE_GSM_USER,
                'password': MOBILE_GSM_PASS
                }

        self._modem.Connecting(opts, timeout=120)

        # Wait up to 3 secs until connected.
        for attempt in range(0, 30):
            if self._modem.State == mm.MM_MODEM_STATE_CONNECTED:
                return True

            time.sleep(0.1)
        return False


    def _disconnect(self):
        """Disconnect packet data connections."""
        
        print 'Disconnecting modem...'
        
        if self._modem.State > mm.MM_MODEM_STATE_REGISTERED: # registered/connected
            try:
                self._modem.Disconnect()
            except dbus.DBusException, e:
                print 'Failed to disconnect the modem: %s' % e
                return False
            
            # Wait up to 3 secs until disconnected.
            for attempt in range(0, 30):
                if self._modem.State < mm.MM_MODEM_STATE_DISCONNECTING:
                    return True

                time.sleep(0.1)
        return True

    
    def up(self):
        assert not self.remote

        if self.is_ready():
            return True
        
        self._enable(False)
        if not self._enable(True):
            return False

        if not self._connect():
            self._enable(False)
            return False

        if not self._pppd_connect():
            return False

        if not super(LinkMobile, self).up():
            return False

        return True

    
    def down(self):
        assert not self.remote
        
        if not self.state or not self._pppd:
            return True

        success = super(LinkMobile, self).down()

        util.set_blocking(self._pppd.stdout.fileno(), True)
        util.set_blocking(self._pppd.stderr.fileno(), True)
        self._pppd.terminate()
        self._pppd = None
        
        self._modem.Disconnect()
        self._modem.Enable(False)

        self.ifname = None
        self.ipaddr = None

        return success


    def is_going_down(self):
        return super(LinkMobile, self).is_going_down()

