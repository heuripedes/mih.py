# vim: ts=8 sts=4 sw=4 et

import os
import re
#import time
import socket
import pickle
import select
import resource

from link import *

#import collections


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

    HOST = 'localhost'
    PORT = 1234

    def __init__(self):
        self._init_mies()
        self._sock = None
        self._peers = []

        self.name = gen_id('MIHF')

    def __str__(self):
        return self.name

    def _make_socket(self, server=True):

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        if server:
            sock.bind((HOST, PORT))
            sock.listen(1)

        sock.setblocking(0)

        return sock

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

    def _refresh_ifaces(self):
        for iface in self._ifaces:
                iface.refresh()
        
    def serve(self):
        self._detect_local_links()

        sock = self._make_socket(server=True)

        while True:
            acceptable, _, _ = select.select([sock], [], [], 300 / 1000.0)

            while readable:
                conn, addr = sock.accept()

                data = conn.recv(resource.getpagesize())
                print data

                readable, writable, erroring = select.select([sock], [], [], 10 / 1000.0)

            self._refresh_ifaces()

        sock.close()

            #time.sleep(300/1000.0) # 300ms

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
    f.serve()

