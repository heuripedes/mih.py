
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

# DBus and ModemManager
import dbus
DBUS_INTERFACE_PROPERTIES='org.freedesktop.DBus.Properties'
MM_DBUS_SERVICE='org.freedesktop.ModemManager'
MM_DBUS_PATH='/org/freedesktop/ModemManager'
MM_DBUS_INTERFACE='org.freedesktop.ModemManager'
MM_DBUS_INTERFACE_MODEM='org.freedesktop.ModemManager.Modem'
MM_DBUS_INTERFACE_MODEM_CDMA='org.freedesktop.ModemManager.Modem.Cdma'
MM_DBUS_INTERFACE_MODEM_GSM_CARD='org.freedesktop.ModemManager.Modem.Gsm.Card'
MM_DBUS_INTERFACE_MODEM_GSM_NETWORK='org.freedesktop.ModemManager.Modem.Gsm.Network'
MM_DBUS_INTERFACE_MODEM_SIMPLE='org.freedesktop.ModemManager.Modem.Simple'

sysbus = dbus.SystemBus()

mm_proxy = None
try:
    mm_proxy = sysbus.get_object(MM_DBUS_SERVICE, MM_DBUS_PATH)
except dbus.DBusException, e:
    print str(e)

mm_iface = None
if mm_proxy:
    mm_iface = dbus.Interface(mm_proxy, dbus_interface=MM_DBUS_INTERFACE)

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
    prefixes = ('lo', 'virbr', 'vboxnet')
    ifnames  = filter(lambda name: not name.startswith(prefixes), sockios.get_iflist())

    # ModemManager not available
    if not mm_iface:
        return ifnames

    # Cell technologies
    #mm_iface.ScanDevices()
    modems = mm_iface.EnumerateDevices()
    for m in modems:
        print m + ":"
        
        import pprint
        link = make_link(ifname=m)
        link.up()
        pprint.pprint(link.as_dict())
        link.down()
        os.abort()
    # with open('/proc/net/dev') as f:
    #     for line in f:
    #         if line.count('|') < 1:
    #             ifname = line.strip().split(':')[0]

    #             if not ifname.startswith(prefixes):
    #                 ifnames.append(ifname)

    return ifnames

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

        self.update(**kwargs)
        #self.poll()

    
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
            self._poll_mac()


    def _poll_mac(self):
        #with open('/sys/class/net/'+self.ifname+'/address') as f:
        #    self.macaddr = f.readline().strip()
        pass


    def _poll_ipv4(self):
        matches = util.match_output('inet ([^/]+)', 'ip -4 -o addr show '+self.ifname)
        self.ipaddr = matches[0] if matches else None


    def poll(self):
        if self.remote:
            return

        before = self.state

        # Link state
        #matches = util.match_output('Link detected: (yes|no)', 'ethtool ' + self.ifname)
        #self.state = matches and matches[0] == 'yes'
        #matches = util.match_output('state (UP|DOWN)', 'ip addr show dev ' + self.ifname)
        #self.state = matches and matches[0] == 'UP'

        self.state = sockios.is_up(self.ifname)

        if before != self.state:
            self._poll_ipv4()


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

        #cmd = 'ip link set up dev '+self.ifname
        #success = (subproc.call(shlex.split(cmd)) == 0)
        
        sockios.set_up(self.ifname)

        self.poll()

        return success and self.state

    
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
        self.wired  = True
        self.wifi   = False
        self.mobile = False

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

#    def down(self):
#        pass


class Link80211(Link):
    def __init__(self, **kwargs):
        self.wired  = False
        self.wifi   = True
        self.mobile = False

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


# TODO: look in https://github.com/openshine/ModemManager/blob/master/test/mm-test.py
#       for inspiration
class LinkMobile(Link):

    def __init__(self, **kwargs):
        self.wired  = False
        self.wifi   = False
        self.mobile = True

        if not kwargs.get('remote'):

            self._proxy = sysbus.get_object(MM_DBUS_INTERFACE, kwargs.get('ifname'))
            self._props = dbus.Interface(self._proxy, dbus_interface=DBUS_INTERFACE_PROPERTIES)
            self._modem = dbus.Interface(self._proxy, dbus_interface=MM_DBUS_INTERFACE_MODEM)
            self._getp = lambda p: self._props.Get(MM_DBUS_INTERFACE_MODEM, p)
            
            types = [None, 'gsm','cdma']
            if self._getp('Type') not in range(1, len(types)):
                raise 'Unsupported modem type.'

            self._dbus_name = kwargs.get('ifname')
            self.m_type   = types[self._getp('Type')]
            self.m_master = self._getp('MasterDevice')
            self.m_device = self._getp('Device')

            kwargs['ifname'] = None

        super(LinkMobile, self).__init__(**kwargs)


    def update(self, *args, **kwargs):
        super(LinkMobile, self).update(*args, **kwargs)
        
        self.ipaddr = None
        self.strenght = 0
        self.samples  = collections.deque(maxlen=WIFI_SAMPLES)

        if self.remote:
            self.strenght =  kwargs.pop('strenght', -1)


    def poll(self):
        if self.remote:
            return
        
        self.state = self._getp('State') == 90 # MM_MODEM_STATE_CONNECTED
        if not state:
            return
        
        net    = dbus.Interface(self._proxy, dbus_interface=MM_DBUS_INTERFACE_MODEM_SIMPLE)
        status = net.GetStatus() 

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

        username = None
        password = None

        if self.m_type == 'gsm':
            username = MOBILE_GSM_USER
            password = MOBILE_GSM_PASS
        
        # TODO: add cdma
        
        if username:
            args += ['user', username]

            # XXX: Setting password this way may be dangerous, check pppd(8).
            #if password: 
            #    args += ['password', password]
        
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
      
        util.set_blocking(self._pppd.stdout.fileno(), False)
        #util.set_blocking(self._pppd.stderr.fileno(), False)
        
        attempts = 200 # 20 segundos
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
      
        #print self.ifname, self.ipaddr, 200-attempts
        if not self.ifname or not self.ipaddr:
            return False

        return True

    def _connect(self):
        """Register the device with a network provider."""

        print 'Connecting modem...'
        opts = None

        if self.m_type == 'gsm':
            opts = {
                    'number':   MOBILE_GSM_NUMBER,
                    'apn':      MOBILE_GSM_APN,
                    'username': MOBILE_GSM_USER,
                    'password': MOBILE_GSM_PASS
                    }
        # TODO: add cdma
        
        net = dbus.Interface(self._proxy, dbus_interface=MM_DBUS_INTERFACE_MODEM_SIMPLE)
        net.Connect(opts, timeout=120)

        # Wait up to 3 secs until connected.
        for attempt in range(0, 30):
            if self._getp('State') == 90:
                return True

            time.sleep(0.1)
        return False

    def _disconnect(self):
        """Disconnect packet data connections."""
        
        print 'Disconnecting modem...'

        if self._getp('State') > 9: # searching, registered or fully connected
            try:
                self._modem.Disconnect()
            except dbus.DBusException, e:
                print 'Failed to disconnect the modem: %s' % e
                return False
            
            # Wait up to 3 secs until disconnected.
            for attempt in range(0, 30):
                if self._getp('State') < 70:
                    return True

                time.sleep(0.1)
        return True

    
    def up(self):
        assert not self.remote

        print 'state:', self._getp('State')

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
        
        print 'state:', self._getp('State')
        
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

