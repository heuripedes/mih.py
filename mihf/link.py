# vim: ts=8 sts=4 sw=4 et ai nu

import collections
import subprocess
import shlex
import re
import util
import time
import os

WIFI_ESSID = 'GREDES_TELEMATICA'
WIFI_KEY   = ''

# get nmcli connection uuid
# nmcli con list | grep ESSID | sed -r 's/.* (([a-f0-9]+-?){5}) .*/\1/'
# nmcli con up UUID

def make_link(*args, **kwargs):
    iface = None
    argdict = {}

    if not kwargs:
        ifname = args[0]
        kwargs['ifname'] = args[0]
    else:
        ifname = kwargs['ifname']

    if os.path.isdir('/sys/class/net/'+ifname+'/wireless'):
        iface = Link80211(**kwargs)
    else:
        iface = Link80203(**kwargs)

    return iface


def detect_local_links():
    """
    Looks for links in /proc/net/dev
    """

    ifnames  = []
    prefixes = ('lo', 'virbr', 'vboxnet')

    with open('/proc/net/dev') as f:
        for line in f:
            if line.count('|') < 1:
                ifname = line.strip().split(':')[0]

                if not ifname.startswith(prefixes):
                    ifnames.append(ifname)

    links = dict()

    for ifname in ifnames:
        iface = make_link(ifname=ifname)

        if iface:
            links[ifname] = iface

    return links


class Link(object):
    def __init__(self, **kwargs):

        self.ifname = ''

        self.state = 'unknown'

        self.mobile   = False
        self.wireless = False
        self.carrier  = False
        self.strenght = 0

        self.ipaddr = None

        # callbacks
        self.on_link_up         = None
        self.on_link_down       = None
        self.on_link_going_down = None

        self.remote = False

        for key in kwargs:
            setattr(self, key, kwargs[key])

        if not self.remote:
            with open('/sys/class/net/'+self.ifname+'/address') as f:
                self.address = f.readline().strip()

    def ready(self):
        return self.state == 'up' and self.ipaddr != None

    def data(self):
        return {
            'ifname'   : self.ifname,
            'state'    : self.state,
            'ipaddr'   : self.ipaddr,
            'carrier'  : self.carrier,
            'wireless' : self.wireless,
            'strenght' : self.strenght,
            'essid'    : getattr(self, 'essid', None)
        }


    #def __str__(self):
    #    return '<%s : %s %s>' \
    #            % (self.__class__.__name__, self.ifname, self.address)

    def poll(self):

        if self.remote:
            return

        with open('/sys/class/net/'+self.ifname+'/operstate') as f:
            self.state = f.readline().strip()

        if self.state == 'up':
            matches = re.findall('inet ([^/]+)',
                    subprocess.check_output(
                        shlex.split('ip -4 -o addr show '+self.ifname)))
            self.ipaddr = matches[0] if matches else None
        else:
            self.ipaddr = None


    def poll_and_notify(self):

        if self.remote:
            return

        last_state = self.state

        self.poll()

        if last_state != self.state:
            if self.ready() and self.on_link_up:
                print "x",self.ifname, self.ready()
                self.on_link_up(self)

            if self.ready() and self.on_link_down:
                self.on_link_down(self)

    def up(self):
        if self.remote:
            print '- Cannot set status on remote links.'
        
        if self.state == 'up':
            return True

        return (subprocess.call(shlex.split('ip link set up dev '+self.ifname)) == 0)


class Link80203(Link):
    def __init__(self, **kwargs):
        super(Link80203, self).__init__(**kwargs)

    def poll(self):
        super(Link80203, self).poll()

        if self.remote:
            return

        if self.state == 'up':
            with open('/sys/class/net/'+self.ifname+'/carrier') as f:
                self.carrier = f.readline().strip() == '1'
        else:
            self.carrier = False

    def up(self):
        before = self.state

        if not super(Link80203, self).up():
            return False
        
        self.poll()
        
        # carrier is plugged in, just need to ask for a new ip
        if self.carrier:
            util.lease_renew(self.ifname)
            
            self.poll()

            if before != self.state and self.ready() and self.on_link_up:
                self.on_link_up(self)
        else:
            print '-', self.ifname+':', 'Carrier not present.'
        
        
class Link80211(Link):
    THRESHOLD = 37
    SAMPLES   = 10

    def __init__(self, **kwargs):
        super(Link80211, self).__init__(**kwargs)

        self.wireless = True
        self.strenght  = 0

        self.samples = collections.deque(maxlen=Link80211.SAMPLES)


    def poll(self):
        super(Link80211, self).poll()

        if self.remote:
            return

        if not self.ready():
            self.strenght = 0
            self.samples.clear()
            self.essid = None
            return

        with open('/sys/class/net/'+self.ifname+'/wireless/link') as f:
            self.strenght = int(f.readline().strip())
            self.samples.append(self.strenght)

        self.essid = re.findall('ESSID:"([^"$]+)',
            subprocess.check_output(shlex.split('iwconfig '+self.ifname)))[0] \
            .strip()


    def poll_and_notify(self):
        if self.remote:
            return

        super(Link80211, self).poll_and_notify()

        if not self.ready():
            return

        if len(self.samples) == Link80211.SAMPLES and util.average(self.samples) < Link80211.THRESHOLD:
            print "Avg:",util.average(self.samples),"Sgn:",self.strenght

            if self.on_link_going_down:
                self.on_link_going_down(self)

    def up(self):
        essid = WIFI_ESSID
        key = WIFI_KEY
        before = self.state

        subprocess.call(['rfkill', 'unblock', 'all'])

        if not super(Link80211, self).up():
            return False
        
        self.poll()


        cmd = ['iwconfig', self.ifname, 'essid', essid]

        if key:
            cmd.append('key')
            cmd.append(key)
        success = subprocess.call(cmd) == 0

        if success:
            success = success and util.lease_renew(self.ifname)

            self.poll()

            #print self.ready()

            if success and before != self.state and self.ready() and self.on_link_up:
                self.on_link_up(self)

        return success

    def scan(self):

        return {
                'GREDES_TELEMATICA': {
                    'nome': 'GREDES_TELEMATICA',
                    'strenght': 60
                    },
                'LABIFTO': {
                    'nome': 'LABIFTO',
                    'strenght': 30
                    }
                }


