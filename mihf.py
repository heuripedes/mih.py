# vim: ts=8 sts=4 sw=4 et

import os
import re
import time
import socket
import select
import resource

from link import *

def gen_id(name):
    """
    :return name+random hex number
    """
    
    return (name.strip() + str(os.urandom(4)).encode('hex_codec')).upper()


class Mihf(object):
    def __init__(self):
        self._init_mies()

        self._sock = None
        self._peers = []

    def __del__(self):
        if self._sock:
            self._sock.close()

    def run(self):
        self._detect_local_links()
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        #self._sock.bind((socket.gethostname(), 1234))
        self._sock.bind(('localhost', 1234))
        self._sock.listen(1)
        self._sock.setblocking(0)

        while 1:
            readable, writable, erroring = select.select([self._sock], [], [], 300/1000.0)

            while readable:
                peer = self._sock.accept()
                print peer[1], 'sent:', peer[0].recv(resource.getpagesize())

                readable, writable, erroring = select.select([self._sock], [], [], 10/1000.0)

            for iface in self._ifaces:
                iface.refresh()

            #time.sleep(300/1000.0) # 300ms

    def _detect_local_links(self):
        """Reads and parses /proc/net/dev"""
        
        ifnames = []

        with open('/proc/net/dev') as f:
            for line in f:
                if line.count('|') < 1:
                    ifnames.append(line.strip().split(':')[0])

        ifnames.remove('lo') # discard loopback

        self._ifaces = []
        
        print '- Detected interfaces:', ', '.join(ifnames)

        for ifname in ifnames:
            if re.match('^eth', ifname):
                self._ifaces.append(Link80203(ifname, self))
            elif re.match('^wlan', ifname):
                self._ifaces.append(Link80211(ifname, self))

        print self._ifaces

    # MIES --------------------------------------------------------------------
    
    def _init_mies(self):
        self.subscribers = dict()

    def subscribe(self, event, receiver):
        if event in self.subscribers:
            self.subscribers[event].append(receiver)
        else:
            self.subscribers[event] = [receiver]
    
    def emit(self, event, sender):
        if not event in self.subscribers:
            return

        for subscriber in self.subscribers[event]:
            if isinstance(subscriber, str):
                print subscriber
            else:
                subscriber(event, sender.mihf, sender)

    # MICS --------------------------------------------------------------------
    
    # MIIS --------------------------------------------------------------------

def on_mih_event(event, mihf, sender):
    print 'Event', event, 'triggered by', sender

if __name__ == '__main__':
    f = Mihf()
    f.subscribe('mih_link_up_indication', on_mih_event)
    f.subscribe('mih_link_down_indication', on_mih_event)
    f.run()

