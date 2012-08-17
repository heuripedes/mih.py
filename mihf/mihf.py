# vim: ts=8 sts=4 sw=4 et ai nu

import os
import sys
import socket
import cPickle
import resource
import collections
import time

from message import *
from link import *
import util

Peer = collections.namedtuple('Peer', 'name, addr')

PAGE_SIZE = resource.getpagesize()

MIHF_PORT  = 12345
MIHF_BCAST = ('255.255.255.255', MIHF_PORT)
MIHF_ANY   = ('0.0.0.0', MIHF_PORT)
MIHF_PEEK_TIME = 10

g_name   = util.gen_id('MIHF')
g_server = False

g_links  = dict()
g_cur_link = None

g_peers  = dict()
g_sock   = None
g_user_handler = None

g_next_peek   = time.time()

__all__ = ['discover', 'report', 'switch', 'serve', 'run', 'local_links', 'remote_links', 'current_link']


def current_link():
    return g_cur_link


def local_links():
    return filter(lambda link: not link.remote, g_links)


def remote_links():
    return filter(lambda link: link.remote, g_links)


def discover(iface):
    assert not g_server

    util.bind_sock_to_device(g_sock, iface.ifname)

    msg = Message(g_name, 'mih_discovery.request', None)

    util.sendto(g_sock, MIHF_BCAST, cPickle.dumps(msg))

    util.bind_sock_to_device(g_sock, '')


def report():
    pass


def switch(link):
    """Switches to another link."""

    global g_cur_link
    global g_next_peek

    if not link.is_ready():
        link.up()

    if not link.is_ready():
        link.down()
        return False

    else:
        #print '- switch():', g_cur_link, '->', link
        
        old_link = g_cur_link
        g_cur_link = link

        if old_link:
            old_link.down()

        
        if link.mobile:
            g_next_peek = time.time() + MIHF_PEEK_TIME

        return True


# TODO: merge link status change handlers into a single handler

def handle_link_up(link):
    print '-', link.ifname, 'is up'

    #if g_server:
    #    bcast_message('mih_link_up.indication', cPickle.dumps(link))

    g_user_handler(link, 'up')


def handle_link_down(link):
    print '-', link.ifname, 'is down'

    #if g_server:
    #    bcast_message('mih_link_down.indication', cPickle.dumps(link))

    g_user_handler(link, 'down')


def handle_link_going_down(link):
    print '-', link.ifname, 'is going down. signal:',link.strenght,'average:',util.average(link.samples)

    #if g_server:
    #    bcast_message('mih_link_going_down.indication', cPickle.dumps(link))
    
    # TODO: request MIH_Report from the server.
    g_user_handler(link, 'going_down')


def export_links():
    """Returns a list of link data suitable for remote use."""

    links = list(g_links.values())

    for link in links:
        link.remote = True
        link.ifname = link.ifname + '@' + g_name

    links = map(lambda link: link.data(), links)

    return links


def handle_message(srcaddr, message):
    # TODO: remove client peer list, it can only talk to one server.

    msgkind = message.kind

    if g_server:
        if msgkind == 'mih_discovery.request':
            print '- Found new peer:', message.source
            p = Peer(message.source, srcaddr)

            g_peers[message.source] = p

            send_message(p, 'mih_discovery.response',
                    cPickle.dumps(export_links()))

    else:
        if msgkind == 'mih_discovery.response':
            print '- Found server:', message.source

            link_data = cPickle.loads(message.payload)

            for data in link_data:
                link = Link(**data)

                print '- Found remote link', link.ifname

            g_peers[message.source] = Peer(message.source, srcaddr)

        #if msgkind == 'mih_link_up.indication':
        #    print '-', cPickle.loads(message.payload).ifname, 'at', message.source, 'is now up.'

        #if msgkind == 'mih_link_down.indication':
        #    print '-', cPickle.loads(message.payload).ifname, 'at', message.source, 'is now down.'

        #if msgkind == 'mih_link_going_down.indication':
        #    print '-', cPickle.loads(message.payload).ifname, 'at', message.source, 'is going down.'


def bcast_message(kind, payload):
    for peer in g_peers.values():
        send_message(peer, kind, payload)


def send_message(peer, kind, payload):
    m = Message(g_name, kind, payload)
    util.sendto(g_sock, peer.addr, cPickle.dumps(m))


def recv_message():
    data, addr = util.recvfrom(g_sock)

    if not data:
        return None, None

    return addr, cPickle.loads(data)


def create_socket():
    global g_sock
    g_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    if g_server:
        g_sock.bind(('0.0.0.0', MIHF_PORT))

    g_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
    g_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, True)

    g_sock.setblocking(False)
    g_sock.settimeout(0.3)


def refresh_links():
    global g_cur_link
    global g_next_peek

    has_ready_links = False

    ifnames = get_local_ifnames()

    new  = filter(lambda ifname: ifname not in g_links, ifnames)
    dead = filter(lambda ifname: ifname not in ifnames, g_links.keys())

    for ifname in new:
        link = make_link(ifname=ifname)

        link.on_link_up   = handle_link_up
        link.on_link_down = handle_link_down
        link.on_link_going_down = handle_link_going_down

        g_links[ifname] = link
            

    for ifname, link in g_links.items():
        if not ifname in dead:
            link.poll_and_notify()

            # server must have as many up links as possible
            if g_server:
                link.up()

            if link.is_ready():
                has_ready_links = True
        else:
            del g_links[ifname]

    # try to turn something up
    if not has_ready_links:
        print "- No up link found, trying to activate one."
        for name, link in g_links.items():
            link.up()

            if link.is_ready():
                g_cur_link = link

                if link.mobile:
                    g_next_peek = time.time() + MIHF_PEEK_TIME

                break

    # Check for available wifi links
    if link.mobile and time.time() > g_next_peek:
        peek_links()
        g_next_peek = g_next_peek + MIHF_PEEK_TIME


def serve(user_handler):
    global g_server
    g_server = True

    run(user_handler)


def run(user_handler):
    global g_user_handler

    g_user_handler = lambda link, state: \
        user_handler(link, state, g_links.values())


    create_socket()

    print '- Starting MIHF', g_name

    if g_server:
        print '- Server mode is on.'

    while True:
        addr, message = recv_message()

        if message:
            handle_message(addr, message)

        refresh_links()
        #time.sleep(0.3)

def peek_links():
    wifi = filter(lambda link: link.wifi, g_links)

    for name, link in wifi.items():
        link.up()

        if not link.is_ready():
            link.down()


