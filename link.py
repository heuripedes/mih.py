# vim: ts=8 sts=4 sw=4 et

import re

class Link(object):
    # from Documentation/networking/operstates.txt

    def __init__(self, ifname):
        self._ifname = ifname

        self._state = 'unknown'

        self.on_link_up = None
        self.on_link_down = None

    @property
    def ifname(self):
        return self._ifname

    def refresh(self):
        operstate = self._state

        with open('/sys/class/net/'+self._ifname+'/operstate') as f:
            operstate = f.readline().strip()

        if operstate != self._state:
            self._state = operstate
            if operstate == 'up' and self.on_link_up:
                self.on_link_up(self)

            if operstate == 'down' and self.on_link_down:
                self.on_link_down(self)
                

class Link80203(Link):
    def __init__(self, ifname):
        super(Link80203, self).__init__(ifname)

class Link80211(Link):
    def __init__(self, ifname):
        super(Link80211, self).__init__(ifname)

