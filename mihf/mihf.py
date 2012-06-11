# vim: ts=8 sts=4 sw=4 et ai nu

import os
import sys
import socket
import cPickle
import resource
import collections
#import time

from message import *
from link import *
import util

Peer = collections.namedtuple('Peer', 'name, addr')

PAGE_SIZE = resource.getpagesize()

MIHF_PORT  = 1234
MIHF_BCAST = ('255.255.255.255', MIHF_PORT)
MIHF_ANY   = ('0.0.0.0', MIHF_PORT)

g_name   = util.gen_id('MIHF')
g_links  = dict()
g_server = False
g_peers  = []
g_sock   = None

__all__ = ['discover', 'report', 'switch', 'serve', 'run']


def discover():
    assert not g_server


def report():
    pass


def switch(link):
    pass


def handle_link_up(link):

    print '-', link.ifname, 'is up'

    if not g_server:
        peer_discovery(link)


    bcast_message('mih_link_up.indication', link.ifname)


def handle_link_down(link):
    print '-', link.ifname, 'is down'

    bcast_message('mih_link_down.indication', link.ifname)


def handle_link_going_down(link):
    print '-', link.ifname, 'is going down'

    bcast_message('mih_link_going_down.indication', link.ifname)

def handle_message(srcaddr, message):
    msgkind = message.kind

    if g_server and msgkind == 'mih_discovery.request':
        print '- Found new peer:', message.source
        p = Peer(message.source, srcaddr)
        g_peers.append(p)
        send_message(p, 'mih_discovery.response', g_links)

    if not g_server and msgkind == 'mih_discovery.response':
        print '- Found server:', message.source
        p = Peer(message.source, srcaddr)
        g_peers.append(p)


def bcast_message(kind, payload):
    for peer in g_peers:
        send_message(peer, kind, payload)


def peer_discovery(iface):

    # TODO: use IP_PKTINFO
    g_sock.setsockopt(socket.SOL_SOCKET, 25, iface.ifname) # 25 = SO_BINDTODEVICE

    msg = Message(g_name, 'mih_discovery.request', None)

    print '>', MIHF_BCAST, msg.kind

    util.sendto(g_sock, MIHF_BCAST, cPickle.dumps(msg))

    g_sock.setsockopt(socket.SOL_SOCKET, 25, '') # 25 = SO_BINDTODEVICE


def send_message(peer, kind, payload):
    m = Message(g_name, kind, payload)
    util.sendto(g_sock, peer.addr, cPickle.dumps(m))
        
    print '>', peer.addr, m.kind

    #peer.sock.sendall(normalize_data(cPickle.dumps(m)))


def recv_message():
    pair = util.recvfrom(g_sock)

    if pair:
        data, addr = pair
        message = cPickle.loads(data)

        print '<', addr, message.kind

        return addr, message

    return None, None

def create_socket():
    global g_sock
    #sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    g_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    if g_server:
        g_sock.bind(('0.0.0.0', MIHF_PORT))
        #sock.listen(1)
    #else:
    #    sock.bind(('255.255.255.255',0))
    
    g_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
    g_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, True)

    g_sock.setblocking(False)
    g_sock.settimeout(0.3)


def refresh_links():
    links = detect_local_links()

    # detect new links
    for key, link in links.items():
        if not key in g_links:
            # TODO: send link up events
            link.on_link_up   = handle_link_up
            link.on_link_down = handle_link_down
            link.on_link_going_down = handle_link_going_down
            g_links[key] = link

    # remove dead links
    for key, link in g_links.items():
        if not key in links:
            # TODO: send link down events
            del g_links[key]
   
    # refresh everything
    for key, link in g_links.items():
        #g_links[key].refresh()
        link.refresh()


def serve():
    global g_server 
    g_server = True

    run()

def run():
    
    create_socket()
   
    print '- Starting MIHF', g_name

    if g_server:
        print '- Server mode is on.'

    while True:
        addr, message = recv_message()

        if message:
            handle_message(addr, message)

        #if not psock:
        #    print '<--',psock[1],psock[0].rstrip('\x00')

        #if not server:
        #    if psock:
        #        util.sendto(sock, psock[1], 'hi there.')
        #    else:
        #        util.sendto(sock, ('255.255.255.255',1234), 'whos there?')
        #else:
        #    if psock:
        #        util.sendto(sock, psock[1], 'hello')

        refresh_links()
        #time.sleep(0.3)


