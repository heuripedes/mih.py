# vim: ts=8 sts=4 sw=4 et

import os
import re
import sys
import time
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

        self.name   = gen_id('MIHF')
        self.links  = dict()
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

    def _refresh_links(self):
        links = detect_local_links()

        # detect new links
        for key, link in links.items():
            if not key in self.links:
                # TODO: send link up events
                link.on_link_up   = self.on_link_up
                link.on_link_down = self.on_link_down
                self.links[key] = link

        # remove dead links
        for key, link in self.links.items():
            if not key in links:
                # TODO: send link down events
                del self.links[key]
       
        # refresh everything
        for key, link in self.links.items():

            self.links[key].refresh()

    def serve(self):
        self._server = True

        self.run()

    def run(self):

        while True:
            self._refresh_links()
            time.sleep(0.3)

        sock.shutdown()
        sock.close()

    # MIES --------------------------------------------------------------------
    # local link -> mihf events
    
    def on_link_up(self, link):
        self.emit('mih_link_up.indication')
        print link.ifname, 'is up'

    def on_link_down(self, link):
        self.emit('mih_link_down.indication')
        print link.ifname, 'is down'
    
    def on_link_going_down(self, link):
        self.emit('mih_link_going_down.indication')
        print link.ifname, 'is going down'

    def subscribe(self, event, receiver):
        matches = re.match('(\w+):(\w.+)', event)

        event = matches.group(2)

        if not matches.group(1) == '@': # not local
            receiver = self.subscribers[matches.group(1)]

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
    if args.server:
        f.serve()
    else:
        f.run()

    return 0

if __name__ == '__main__':
    sys.exit(main())

