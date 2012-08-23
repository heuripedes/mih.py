# vim: ts=8 sts=4 sw=4 et ai nu

import os
import sys
import socket
import cPickle
import collections
import time

import logging 
logger = logging#logging.getLogger()
logger.basicConfig(format='(%(filename)s:%(lineno)d) %(levelname)s: %(message)s',level=logging.DEBUG)#logger.setLevel(logging.INFO)

from message import *
from link import *
import util

Peer = collections.namedtuple('Peer', 'name, addr')

MIHF_PORT  = 12345
MIHF_PEEK_TIME = 10

__all__ = ['discover', 'report', 'switch', 'serve', 'run', 'local_links', 'remote_links', 'current_link']

class MihfState(object):
    def __init__(self):
        self.name   = util.gen_id('MIHF-')
        self.server = False
        self.links  = dict()
        self.cur_link = None
        self.peers  = dict()
        self.sock   = None
        self.user_handler = None
        self.next_peek = time.time()

g = MihfState()

def current_link():
    return g.cur_link


def local_links():
    return filter(lambda link: not link.remote, g.links)


def remote_links():
    return filter(lambda link: link.remote, g.links)


def discover(iface):
    assert not g.server

    util.bind_sock_to_device(g.sock, iface.ifname)

    msg = Message(g.name, 'mih_discovery.request')

    #util.sendto(g.sock, (socket.INADDR_BROADCAST, MIHF_PORT), msg.pickle())
    util.sendto(g.sock, ('<broadcast>', MIHF_PORT), msg.pickle())

    util.bind_sock_to_device(g.sock, '')


def report():
    pass


def switch(link):
    """Switches to another link."""
    
    if not link.up():
        link.down()
        return False
    
    if g.cur_link:
        g.cur_link.down()
    
    if link.mobile:
        g.next_peek = time.time() + MIHF_PEEK_TIME

    g.cur_link = link

    return True


def handle_link_state_change(link, state):
    logger.info('Link %s is %s', link.ifname, state)

    g.user_handler(link, state)


def export_links():
    """Returns a list of link data suitable for remote use."""

    links = []

    for l in g.links.values():
        link = l.as_dict()
        link['remote'] = True
        link['ifname'] = l.ifname + '@' + g.name
        links.append(link)

    return links


def handle_message(srcaddr, message):
    # TODO: remove client peer list, it can only talk to one server.

    msgkind = message.kind

    if g.server:
        if msgkind == 'mih_discovery.request':
            logger.info('New peer found: %s', message.src)

            p = Peer(message.src, srcaddr)

            g.peers[message.src] = p

            #send_message(p, 'mih_discovery.response',
            #        cPickle.dumps(export_links()))
            send_message(p, 'mih_discovery.response', export_links())

    else:
        if msgkind == 'mih_discovery.response':

            if message.src not in g.peers:
                logger.info('New server found: %s', message.src)

                for data in message.payload:
                    link = Link(**data)

                    logger.info('Remote link found: %s', link)

                g.peers[message.src] = Peer(message.src, srcaddr)

        #if msgkind == 'mih_link_up.indication':
        #    print '-', cPickle.loads(message.payload).ifname, 'at', message.src, 'is now up.'

        #if msgkind == 'mih_link_down.indication':
        #    print '-', cPickle.loads(message.payload).ifname, 'at', message.src, 'is now down.'

        #if msgkind == 'mih_link_going_down.indication':
        #    print '-', cPickle.loads(message.payload).ifname, 'at', message.src, 'is going down.'


def bcast_message(kind, payload):
    for peer in g.peers.values():
        send_message(peer, kind, payload)


# TODO: use Message's parent field
def send_message(peer, kind, payload):
    m = Message(g.name, kind, payload, dst=peer.name)
    util.sendto(g.sock, peer.addr, m.pickle())


def recv_message():
    data, addr = util.recvfrom(g.sock)

    if not data:
        return None, None

    return addr, cPickle.loads(data)


def create_socket():
    g.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    if g.server:
        #g.sock.bind((socket.INADDR_ANY, MIHF_PORT))
        g.sock.bind(('', MIHF_PORT))

    g.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
    g.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, True)

    g.sock.setblocking(False)
    g.sock.settimeout(0.3)


def refresh_links():

    has_ready_links = False

    ifnames = get_local_ifnames()

    new  = filter(lambda ifname: ifname not in g.links, ifnames)
    dead = filter(lambda ifname: ifname not in ifnames, g.links.keys())

    for ifname in new:
        link = make_link(ifname=ifname)

        link.on_link_state_change = handle_link_state_change

        g.links[ifname] = link
            

    for ifname, link in g.links.items():
        if not ifname in dead:
            link.poll_and_notify()

            # server must have as many up links as possible
            if g.server and not link.remote:
                link.up()

            if link.is_ready():
                has_ready_links = True
        else:
            del g.links[ifname]

    # try to turn something up
    if not has_ready_links:
        logger.warning('No active link found, trying to activate one.')
        for name, link in g.links.items():
            link.up()

            if link.is_ready():
                g.cur_link = link

                if link.mobile:
                    g.next_peek = time.time() + MIHF_PEEK_TIME

                break

    # Check for available wifi links
    if link.mobile and time.time() > g.next_peek:
        peek_links()
        g.next_peek = g.next_peek + MIHF_PEEK_TIME


def serve(user_handler):
    g.server = True

    run(user_handler)


def run(user_handler):

    g.user_handler = lambda link, state: \
        user_handler(link, state, g.links.values())


    create_socket()

    logger.info('Starting MIHF %s', g.name)
    logger.info('Server mode is %s', 'on' if g.server else 'off')

    while True:
        addr, message = recv_message()
        
        if message:
            handle_message(addr, message)

        refresh_links()

        #time.sleep(0.3)

def peek_links():
    wifi = filter(lambda link: link.wifi, g.links)

    for name, link in wifi.items():
        link.up()

        if not link.is_ready():
            link.down()


