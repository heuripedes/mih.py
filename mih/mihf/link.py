
import os
import collections
#import errno
import shlex
import subprocess as subproc
import re
import util

import sockios

sockios.init()

WIRED_UP_STRENGHT   = 1000
WIRED_DOWN_STRENGHT = 0
    

WIFI_ESSID = 'GREDES_TELEMATICA'
WIFI_KEY   = ''

WIFI_THRESHOLD = 37
WIFI_SAMPLES   = 10

def get_local_ifnames():
    """
    Looks for links in /proc/net/dev
    """

    
    prefixes = ('lo', 'virbr', 'vboxnet')
    ifnames  = filter(lambda name: not name.startswith(prefixes), sockios.get_iflist())

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
    
    # TODO: Add check for mobile links.
    if os.path.isdir('/sys/class/net/'+kwargs.get('ifname')+'/wireless'):
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
                (self.__class__.__name__, self.ifname, self.ipaddr)


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
            self.macaddr = kwargs.pop('macaddr', None)
            self.ipaddr  = kwargs.pop('ipaddr', None)
            self.state    =  kwargs.pop('state', False)

        else:
            self._poll_mac()

    def _poll_mac(self):
        with open('/sys/class/net/'+self.ifname+'/address') as f:
            self.macaddr = f.readline().strip()


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

        super(LinkMobile, self).__init__(**kwargs)

    def update(self, *args, **kwargs):
        super(LinkMobile, self).update(*args, **kwargs)

    def poll(self):
        super(LinkMobile, self).poll()

    def poll_and_notify(self):
        super(LinkMobile, self).poll_and_notify()

    def up(self):
        return super(LinkMobile, self).up():

    def is_going_down(self):
        return super(LinkMobile, self).is_going_down():

