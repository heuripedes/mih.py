# vim: ts=8 sts=4 sw=4 et

import os
import re
import sys
#import time
import socket
import cPickle
import select
import resource
import argparse

from message import *
from link import *

import collections

PAGE_SIZE = resource.getpagesize()


def gen_id(name):
    """
    :return name+random hex number
    """

    return (name.strip() + '-' + str(os.urandom(4)).encode('hex_codec')).upper()

Peer = collections.namedtuple('Peer', 'name, sock, addr')

class Mihf(object):

    HOST = 'localhost'
    PORT = 1234

    def __init__(self):
        self._init_mies()
        self._sock = None


        self._iqueue = [] # incoming
        self._oqueue = [] # outcoming

        self.name   = gen_id('MIHF')
        self.peers  = []
        self.links  = []
        self.server = False

    def __str__(self):
        return self.name

    # MICS / MIIS
    
    def discover(self):
        """
        Discovers server MIHFs in the active networks.
        """
        pass

    def report(self):
        """
        Returns information about a MIHF.
        """
        pass
    
    def switch(self, link):
        """
        Switch to another link.
        """
        pass

    def _make_socket(self, server=True):

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        if server:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, True)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
            sock.bind(('0.0.0.0', self.PORT))
            sock.listen(1)
        #else:
            #sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
            #sock.bind((self.HOST, self.PORT))

        sock.setblocking(0)

        return sock




    def _add_peer(self, peer):
        """
        Add a new peer. *peer* must be an instance of the Peer named tuple.
        """ 

        self.peers[peer.name] = peer

    def _remove_peer(self, peer):
        """
        Remove a peer. *peer* can either be the name of the peer, its socket 
        or an instance of the Peer named tuple.
        """

        if isinstance(peer, str):
            del self.peers[name]
        elif isinstance(peer, socket):
            for key, p in self.peers[name]:
                if p.sock == peer:
                    self.peers[key]
                    return
        else:
            del self.peers[peer.name]

    def _check_peers(self, sock):

        assert self._server

        # check for new peers
        acceptable, _, _ = select.select([sock], [], [], 300 / 1000.0)

        while acceptable:
            client, addr = sock.accept()
            data = client.recv(PAGE_SIZE)

            msg = cPickle.loads(data)

            peer = Peer(msg.src, client, addr)

            client.setblocking(False)

            self._add_peer(peer)

            print "- New peer: ", peer

            acceptable, _, _ = select.select([sock], [], [], 10 / 1000.0)

    def _discover(self, sock):
        if not self.links:
            print 'No interfaces detected.'
            sys.exit(-1)

        for iface in self.links:
            if iface.state == 'up' and self.carrier:
                sock.setsockopt(socket.SOL_SOCKET, 25, iface.ifname) # 25 = SO_BINDTODEVICE
                msg = Message.request(self.name, None, None, 'MIH_Discovery', None)
                self._send(msg)

        sock.setsockopt(socket.SOL_SOCKET, 25, '') # 25 = SO_BINDTODEVICE

    def _synchronize(self, sock):
        """Receive and/or send queued messages"""

        if not self.peers:
            # flush oqueue
            return

        # NOTE: recv() and send() might not receive/send all the data

        for key, peer in self.peers:
            try:
                data = peer.sock.recv(PAGE_SIZE)

                print data

                if data:
                    self._iqueue.append(cPickle.loads(data))

            except socket.error, msg:
                print msg
        
        if self._oqueue:
            for msg in self._oqueue:
                
                if not msg.dest in self.peers:
                    print "- Peer not found:", msg.dest
                    self._oqueue.remove(msg)
                    continue

                data = msg.ljust(PAGE_SIZE, '\x00')
               
                try:
                    peer = self.peers[msg.dest]
                    peer.sock.send(data)
                except socket.error, msg:
                    print msg

    def _send(self, what):
        sock.send(what)
        #self._oqueue.append(what)

    def _recv(self):
        if self._iqueue:
            return self._iqueue.pop()
        else:
            return None

    def _refresh_links(self):
        links = detect_local_links()

        # detect new links
        for key, value in links:
            if not key in self.links:
                # TODO: send link up events
                self.links[key] = value

        # remove dead links
        for key, value in self.links:
            if not key in links:
                # TODO: send link down events
                del self.links[key]
       
        # refresh everything
        for key, link in self.links:
            self.links[key].refresh()

    def serve(self):
        self._server = True

        self.run()

    def run(self):

        sock = self._make_socket(self._server)
        

        while True:

            self._refresh_links()

            for key, peer in self.peers:
                try:
                    data = peer.sock.recv(PAGE_SIZE)

                    print data

                    if data:
                        self._iqueue.append(cPickle.loads(data))

                except socket.error, msg:
                    print msg
                data = peer
            self._synchronize(sock)

            for link in self.links:
                link.refresh()

        sock.shutdown()
        sock.close()

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


def parse_args(argv):

    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser()

    parser.add_argument('-s', '--server',
            action='store_true', help='Run as MIH server')

    return parser.parse_args(argv)

def main(argv=None):

    args = parse_args(argv)

#    print args

    f = Mihf()
    f.subscribe('mih_link_up_indication', on_mih_event)
    f.subscribe('mih_link_down_indication', on_mih_event)



#    print str(f)
#    print Message.indication(str(f), str(f), 'MIES', 'mih_link_up', 'eth0')
#
    if args.server:
        f.serve()
    else:
        f.run()

    return 0

if __name__ == '__main__':
    sys.exit(main())

