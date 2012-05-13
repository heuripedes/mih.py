# vim: ts=8 sts=4 sw=4 et

import os
import re
import time
import socket
import pickle

from link import *

import collections

def gen_id(name):
    """
    :return name+random hex number
    """
    
    return (name.strip() + '-' + str(os.urandom(4)).encode('hex_codec')).upper()

class Message:
    def __init__(self, src, dest, service, operation, action, payload):
        self.src, self.dest = src, dest
        self.service, self.operation, self.action = service, operation, action
        self.payload = payload

    def __str__(self):
        return pickle.dumps(self) 

    @staticmethod
    def request(src, dest, service, action, payload):
        return Message(str(src), str(dest), service, 'request', action, payload)

    @staticmethod
    def response(src, dest, service, action, payload):
        return Message(str(src), str(dest), service, 'response', action, payload)

    @staticmethod
    def indication(src, dest, service, action, payload):
        return Message(str(src), str(dest), service, 'indication', action, payload)

class Mihf(object):
    def __init__(self):
        self._init_mies()

        self._sock = None
        self._peers = []

        self.name = gen_id('MIHF')

    def __del__(self):
        if self._sock:
            self._sock.close()

    def __str__(self):
        return self.name

    def run(self):
        import select
        import resource

        self._detect_local_links()
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        #self._sock.bind((socket.gethostname(), 1234))
        self._sock.bind(('localhost', 1234))
        self._sock.listen(1)
        self._sock.setblocking(0)

        while 1:
            readable, _, _ = select.select([self._sock], [], [], 300/1000.0)

            while readable:
                conn, addr = self._sock.accept()

                data = conn.recv(resource.getpagesize())
                print data

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
            iface = None
            if re.match('^eth', ifname):
                iface = Link80203(ifname)
            elif re.match('^wlan', ifname):
                iface = Link80211(ifname)

            if iface:
                iface.on_link_up = self.on_link_up
                iface.on_link_down = self.on_link_down
                self._ifaces.append(iface)


        #print self._ifaces

    # MIES --------------------------------------------------------------------
    
    def _init_mies(self):
        self.subscribers = dict()

    def on_link_up(self, link):
        print link.ifname, 'is up'

    def on_link_down(self, link):
        print link.ifname, 'is down'

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

#    print str(f)
#    print Message.indication(str(f), str(f), 'MIES', 'mih_link_up', 'eth0')
    f.run()

