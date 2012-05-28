# vim: ts=8 sts=4 sw=4 et

import re

def make_link(ifname):
    iface = None

    if re.match('^eth', ifname):
        iface = Link80203(ifname)
    elif re.match('^wlan', ifname):
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

    links = []

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

        # callbacks
        self.on_link_up = None
        self.on_link_down = None

        with open('/sys/class/net/'+self.ifname+'/address') as f:
            self.address = f.readline().strip()

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
                

class Link80203(Link):
    def __init__(self, ifname):
        super(Link80203, self).__init__(ifname)

    def refresh(self):
        with open('/sys/class/net/'+self.ifname+'/carrier') as f:
            self.carrier = f.readline().strip() == '1'

        super(Link80203, self).refresh()

class Link80211(Link):
    def __init__(self, ifname):
        super(Link80211, self).__init__(ifname)

        self.wireless = True
   
    def refresh(self):
        #'/sys/class/net/'+self.ifname+'/wireless/'
        super(Link80211, self).refresh()

