# vim: ts=8 sts=4 sw=4 et

import os
import re
#import time
import socket
import pickle
import select
import resource

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

Peer = collections.namedtuple('Peer', 'name, sock, addr')

class Mihf(object):

    HOST = 'localhost'
    PORT = 1234

    def __init__(self):
        self._init_mies()
        self._sock = None

        # TODO: self._peers must be a dict (id -> { sock, addr })
        self._peers = []
        self._server = False

        # TODO: finish in/out queue implementation
        self._iqueue = [] # incoming
        self._oqueue = [] # outcoming

        self.name = gen_id('MIHF')

    def __str__(self):
        return self.name

    def _make_socket(self, server=True):

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        #if server:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, True)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
        sock.bind(('0.0.0.0', self.PORT))
        sock.listen(1)
        #else:
        #sock.bind((self.HOST, self.PORT))

        sock.setblocking(0)

        return sock

    def _detect_local_links(self):
        """Reads and parses /proc/net/dev"""

        ifnames = []

        with open('/proc/net/dev') as f:
            for line in f:
                if line.count('|') < 1:
                    ifname = line.strip().split(':')[0]
                    if not ifname == 'lo':
                        ifnames.append(ifname)

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

        print self._ifaces[0]

    def _check_peers(self, sock):


        # check for new peers
        acceptable, _, _ = select.select([sock], [], [], 300 / 1000.0)

        while acceptable:
            self._peers.append(sock.accept()[0])
            acceptable, _, _ = select.select([sock], [], [], 10 / 1000.0)


    def _sync(self, sock):
        """Receive and/or send queued messages"""

        if not self._peers:
            #print "- Flushing message queues."
            pass

        rlist, wlist, xlist = select.select(self._peers, self._peers, self._peers, 100 / 1000.0)

        # receive messages
        for psock in rlist:
            # TODO: use recvfrom and refresh self._peers
            data = psock.recv(resource.getpagesize())

            if not data:
                self._peers.remove(psock)

                if psock in wlist:
                    wlist.remove(psock)
            else:
                self._iqueue.append(data)
                print data

        # send messages
        if self._oqueue:
            for psock in wlist:
                pass
    
    def _send(self, what):
        self._oqueue.append(what)

    def _recv(self):
        if self._iqueue:
            return self._iqueue.pop()
        else:
            return None

        
    def serve(self):
        self._detect_local_links()

        sock = self._make_socket(server=True)

        self._server = True

        while True:

            self._check_peers(sock)
            self._sync(sock)

            for iface in self._ifaces:
                iface.refresh()

        sock.shutdown()
        sock.close()

    def run(self):
        self._detect_local_links()

        sock = self._make_socket(server=False)

        while True:
            pass

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

