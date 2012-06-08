# vim: ts=8 sts=4 sw=4 et ai nu

import os
import re
import sys
import time
import socket
import cPickle
import select
import resource
import argparse
import collections

from message import *
from link import *
import util


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
        self.name   = gen_id('MIHF')
        self.links  = dict()
        self.server = False
        self.peers  = []

    def __del__(self):
        if self.sock:
            #self.sock.shutdown()
            self.sock.close()

    def __str__(self):
        return self.name

    # MICS / MIIS
    
    def discover(self):
        """
        Discovers server MIHFs in the active networks.
        """
        assert not self.server

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

    def run(self):
        self._main_loop()

    # local link events
    def _link_up_event(self, link):
        self._discovery(link)

        self._bcast_message('mih_link_up.indication', link.ifname)
        print link.ifname, 'is up'

    def _link_down_event(self, link):
        self._bcast_message('mih_link_down.indication', link.ifname)
        print link.ifname, 'is down'
    
    def _link_going_down_event(self, link):
        self._bcast_message('mih_link_going_down.indication', link.ifname)
        print link.ifname, 'is going down'

    # networking 
    def _bcast_message(self, kind, payload):
        for peer in self.peers:
            self._send_message(peer, kind, payload)
        return

    def _discovery(self, iface):
        #util.sendto(self.sock, ('255.255.255.255',1234), 'whos there?')there
        pass

    def _send_message(self, peer, kind, payload):
        m = Message(self.name, kind, payload)
        peer.sock.sendall(normalize_data(cPickle.dumps(m)))

    def _recv_message(self, peer):
        data = peer.sock.recv(PAGE_SIZE)
        return cPickle.loads(data)

    def _create_socket(self):
        #self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        if self.server:
            self.sock.bind(('0.0.0.0', self.PORT))
            #self.sock.listen(1)
        #else:
        #    self.sock.bind(('255.255.255.255',0))
        
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, True)

        self.sock.setblocking(False)
        self.sock.settimeout(0.3)
   
    def _main_loop(self):
        
        self._create_socket()

        print self.sock.getsockname()

        while True:
            pair = util.recvfrom(self.sock)
            message = None

            if pair:
                data, addr = pair
                message = cPickle.loads(data)

            if message:
                print message.source, message.kind

            #if not psock:
            #    print '<--',psock[1],psock[0].rstrip('\x00')

            #if not self.server:
            #    if psock:
            #        util.sendto(self.sock, psock[1], 'hi there.')
            #    else:
            #        util.sendto(self.sock, ('255.255.255.255',1234), 'whos there?')
            #else:
            #    if psock:
            #        util.sendto(self.sock, psock[1], 'hello')

            self._refresh_links()
            time.sleep(0.3)

    def _refresh_links(self):
        links = detect_local_links()

        # detect new links
        for key, link in links.items():
            if not key in self.links:
                # TODO: send link up events
                link.on_link_up   = self._link_up_event
                link.on_link_down = self._link_down_event
                link.on_link_going_down = self._link_going_down_event
                self.links[key] = link

        # remove dead links
        for key, link in self.links.items():
            if not key in links:
                # TODO: send link down events
                del self.links[key]
       
        # refresh everything
        for key, link in self.links.items():

            self.links[key].refresh()

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

#    print str(f)
#    print Message.indication(str(f), str(f), 'MIES', 'mih_link_up', 'eth0')
#

    f.server = args.server
    f.run()

    return 0

if __name__ == '__main__':
    sys.exit(main())

