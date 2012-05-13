# vim: ts=8 sts=4 sw=4 et

import re

class Link(object):
    # from Documentation/networking/operstates.txt
    UNKNOWN = 0
    DOWN    = 2
    UP      = 6

    def __init__(self, ifname, mihf):
        """Constructor"""
        self._ifname = ifname
        self._mihf   = mihf

        self._state = self.UNKNOWN

    @property
    def mihf(self):
        return self._mihf

    @property
    def ifname(self):
        return self._ifname

    def refresh(self):
        operstate = None

        with open('/sys/class/net/'+self._ifname+'/operstate') as f:
            operstate = f.readline() 

        if re.match('^up', operstate) and not self._state == self.UP:
            self._state = self.UP
            self._mihf.emit('mih_link_up_indication', self)

        if re.match('^down', operstate) and not self._state == self.DOWN:
            self._state = self.DOWN
            self._mihf.emit('mih_link_down_indication', self)


class Link80203(Link):
    def __init__(self, ifname, mihf):
        super(Link80203, self).__init__(ifname, mihf)

class Link80211(Link):
    def __init__(self, ifname, mihf):
        super(Link80211, self).__init__(ifname, mihf)

