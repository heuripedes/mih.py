# vim: ts=8 sts=4 sw=4 et ai nu

import collections
import subprocess
import shlex
import re
import util

def make_link(ifname):
    iface = None

    if ifname.startswith('eth'):
        iface = Link80203(ifname)
    elif ifname.startswith('wlan'):
        iface = Link80211(ifname)

    return iface


def detect_local_links():
    """
    Looks for links in /proc/net/dev
    """

    ifnames = []

    with open('/proc/net/dev') as f:
        for line in f:
            if line.count('|') < 1:
                ifname = line.strip().split(':')[0]
                if not ifname == 'lo':
                    ifnames.append(ifname)

    links = dict()

    #print '- Detected interfaces:', ', '.join(ifnames)

    for ifname in ifnames:
        iface = make_link(ifname)

        if iface:
            #iface.on_link_up = self.on_link_up
            #iface.on_link_down = self.on_link_down
            #links.append(iface)
            links[ifname] = iface

    return links

class Link(object):
    def __init__(self, ifname):
        self.ifname = ifname

        self.state = 'unknown'

        self.wireless = False
        self.carrier  = False
        self.strenght = 0

        self.ipaddr = ''

        # callbacks
        self.on_link_up = None
        self.on_link_down = None
        self.on_link_going_down = None

        with open('/sys/class/net/'+self.ifname+'/address') as f:
            self.address = f.readline().strip()

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

        #d = LinkData(
        #    ifname=self.ifname, 
        #    state=self.state,
        #    ipaddr=self.ipaddr,
        #    carrier=self.carrier,
        #    wireless=self.wireless,
        #    strenght=self.strenght)

        #if hasattr(self, 'essid'):
        #    d.essid = self.essid

        #return d

    def __str__(self):
        return '<%s : %s %s>' \
                % (self.__class__.__name__, self.ifname, self.address)

    def refresh(self):
        operstate = self.state

        with open('/sys/class/net/'+self.ifname+'/operstate') as f:
            operstate = f.readline().strip()

        if operstate != self.state:
            self.state = operstate
            if operstate == 'up' and self.on_link_up:
                self.on_link_up(self)

            if operstate == 'down' and self.on_link_down:
                self.on_link_down(self)
       
        if self.state == 'up':
            self.ipaddr = re.findall('inet ([^/]+)',
                subprocess.check_output(
                    shlex.split('ip -4 -o addr show '+self.ifname)))[0]
        else:
            self.ipaddr = None

                

class Link80203(Link):
    def __init__(self, ifname):
        super(Link80203, self).__init__(ifname)

    def refresh(self):
        with open('/sys/class/net/'+self.ifname+'/carrier') as f:
            self.carrier = f.readline().strip() == '1'

        super(Link80203, self).refresh()

class Link80211(Link):
    THRESHOLD = 37
    SAMPLES   = 100

    def __init__(self, ifname):
        super(Link80211, self).__init__(ifname)

        self.wireless = True
        self.quality  = 0

        self.qualities = collections.deque(maxlen=100)
   
    def refresh(self):
        super(Link80211, self).refresh()
        
        if not self.state == 'up':
            self.quality = 0
            self.qualities.clear()
            self.essid = None
            return
        
        with open('/sys/class/net/'+self.ifname+'/wireless/link') as f:
            self.quality = f.readline().strip()
            self.qualities.append(self.quality)

         
        self.essid = re.findall('ESSID:"([^"$]+)',
            subprocess.check_output(shlex.split('iwconfig '+self.ifname)))[0] \
            .strip()

