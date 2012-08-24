# vim: ts=8 sts=4 sw=4 et ai nu



# def switch(link):
#     """Switches to another link."""
    
#     if not link.up():
#         link.down()
#         return False
    
#     if g.cur_link:
#         g.cur_link.down()
    
#     if link.mobile:
#         g.next_peek = time.time() + MIHF_PEEK_TIME

#     g.cur_link = link

#     return True



# def handle_message(srcaddr, message):
#     # TODO: remove client peer list, it can only talk to one server.

#     msgkind = message.kind

#     if g.server:
#         if msgkind == 'mih_discovery.request':
#             logger.info('New peer found: %s', message.src)

#             p = Peer(message.src, srcaddr)

#             g.peers[message.src] = p

#             #send_message(p, 'mih_discovery.response',
#             #        cPickle.dumps(export_links()))
#             send_message(p, 'mih_discovery.response', export_links())

#     else:
#         if msgkind == 'mih_discovery.response':

#             if message.src not in g.peers:
#                 logger.info('New server found: %s', message.src)

#                 for data in message.payload:
#                     link = Link(**data)

#                     logger.info('Remote link found: %s', link)

#                 g.peers[message.src] = Peer(message.src, srcaddr)

#         #if msgkind == 'mih_link_up.indication':
#         #    print '-', cPickle.loads(message.payload).ifname, 'at', message.src, 'is now up.'

#         #if msgkind == 'mih_link_down.indication':
#         #    print '-', cPickle.loads(message.payload).ifname, 'at', message.src, 'is now down.'

#         #if msgkind == 'mih_link_going_down.indication':
#         #    print '-', cPickle.loads(message.payload).ifname, 'at', message.src, 'is going down.'


# def refresh_links():

#     has_ready_links = False

#     ifnames = get_local_ifnames()

#     new  = filter(lambda ifname: ifname not in g.links, ifnames)
#     dead = filter(lambda ifname: ifname not in ifnames, g.links.keys())

#     for ifname in new:
#         link = make_link(ifname=ifname)

#         link.on_link_event = handle_link_state_change

#         g.links[ifname] = link
            

#     for ifname, link in g.links.items():
#         if not ifname in dead:
#             link.poll_and_notify()

#             # server must have as many up links as possible
#             if g.server and not link.remote:
#                 link.up()

#             if link.is_ready():
#                 has_ready_links = True
#         else:
#             del g.links[ifname]

#     # try to turn something up
#     if not has_ready_links:
#         logger.warning('No active link found, trying to activate one.')
#         for name, link in g.links.items():
#             link.up()

#             if link.is_ready():
#                 g.cur_link = link

#                 if link.mobile:
#                     g.next_peek = time.time() + MIHF_PEEK_TIME

#                 break

#     # Check for available wifi links
#     if link.mobile and time.time() > g.next_peek:
#         peek_links()
#         g.next_peek = g.next_peek + MIHF_PEEK_TIME


# def peek_links():
#     wifi = filter(lambda link: link.wifi, g.links)

#     for name, link in wifi.items():
#         link.up()

#         if not link.is_ready():
#             link.down()


import time
import socket
import select

import logging 


import util
from link import *
from message import Message

class BasicMihf(object):
    """This class describes the common operations that all MIHFs classes 
    should implement"""

    def __init__(self):
        pass

    # accessors
    @property
    def links(self):
        return self._links.values()
    
    @property
    def name(self):
        return self._name

    # MIH Commands
    def discover(self, link):
        """Broadcasts a server discovery request throught *link*. *link* 
        can either be a Link instance or a string containing the interface 
        name."""
        raise NotImplemented

    def switch(self, link):
        """Switches to the link described by *link*."""
        raise NotImplemented

    def report(self, links=[]):
        """Return information about the links in *links*."""
        raise NotImplemented


class LocalMihf(BasicMihf):
    def __init__(self, handler, port=12345, peek_time=10):
        super(LocalMihf, self).__init__()

        self._name    = util.gen_id('MIHF-')
        self._curlink = None
        self._links   = dict()
        self._peers   = dict()
        self._sock    = None
        self._handler = handler
        self._port    = port
        self._next_peek = time.time()
        self._peek_time = peek_time


    def discover(self, link):

        if not isinstance(link, str):
            link = link.ifname

        util.bind_sock_to_device(self._sock, link)
    
        self._send(('<broadcast>', self._port), 'mih_discovery.request')

        util.bind_sock_to_device(self._sock, '')


    def switch(self, link):

        if not link.up():
            link.down()
            return False
        
        if self._curlink:
            self._curlink.down()
        
        if link.mobile:
            self._next_peek = time.time() + self._peek_time

        self._curlink = link

        return True
    
    

    def _make_socket(self, bind=False, blocking=False, timeout=0.3):

        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        if bind:
            self._sock.bind(('', self._port))

        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, True)

        self._sock.setblocking(blocking)
        self._sock.settimeout(timeout)
        
    
    def _send(self, dest, kind, payload=None, parent=None):
        """Sends a message to *dest*.
        
        *dest* is an *(host, port)* tuple. Alternatively, *dest* can be a 
        string with the peer name.
        
        *kind*, *payload* and *parent* are passed to the Message class 
        constructor."""

        assert isinstance(dest, tuple) or isinstance(dest, str)

        msg = Message(self._name, kind, payload, parent=parent)

        if isinstance(dest, str):
            dest = self._peers[dest].addr

        msg.parent = parent

        util.sendto(self._sock, dest, util.pickle(msg))

    
    def _receive(self):
        """Attempts to read a message from the socket."""
        
        if not select.select([self._sock],[],[], 0):
            return None, None
        
        data, addr = util.recvfrom(self._sock)

        if not data:
            return None, None

        return addr, util.unpickle(data)


    def _handle_message(self, srcaddr, msg):
        pass


    def _handle_link_event(self, link, state):
        logging.info('Link %s is %s', link, state)

        self._notify_user(link, state)


    def _notify_user(self, link, state):
        self._handler(self, link, state)


    def _export_links(self):
        """Returns a list of link data suitable for remote use."""

        exported = []

        for link in self._links.values():
            d = link.as_dict()
            d['remote'] = True
            
            exported.append(d)

        return exported

    def _refresh_links(self):
        
        llnames = get_local_ifnames()
        new  = list(set(llnames) - set(self._links.keys()))
        dead = list(set(self._links.keys()) - set(llnames))

        print 'local ifnames',llnames
        
        for name in dead:
            # TODO: send link down?
            del self._links[name]

        for name in new:
            link = make_link(ifname=name)
            link.on_link_event = self._handle_link_event
            self._links[name] = link

        ready = []

        for name, link in self._links.items():
            link.poll_and_notify()

            if link.is_ready():
                ready.append(link)

        on_mobile = self._curlink and self._curlink.mobile 

        if on_mobile and time.time() > self._next_peek:
            self.peek_links()
            self._next_peek += self._peek_time

        return ready

    def peek_links(self):
        wifi = filter(lambda link: link.wifi, g.links)

        for name, link in wifi.items():
            if not link.up():
                link.down()


class RemoteMihf(BasicMihf):
    def __init__(self, name, addr, links=dict()):
        super(RemoteMihf, self).__init__()
        
        self._name  = name
        self._addr  = addr
        self._links = links

    @property
    def addr(self):
        return self._addr

    @property
    def links(self):
        return self._links.values()

    @links.setter
    def links(self, links):
        self._links = links

    def import_links(self, links):
        for link in links:
            self._links[link['ifname']] = Link(**link)


class ClientMihf(LocalMihf):
    def __init__(self, handler, port=12345):
        super(ClientMihf, self).__init__(handler, port)
    
    def run(self):
        logging.info('Starting client MIHF %s', self._name)

        self._make_socket()

        while True:
            addr, msg = self._receive()

            if msg:
                self._handle_message(addr, msg)

            ready = self._refresh_links()

            if not ready:
                for link in self._links.values():
                    if self.switch(link):
                        break


    def _handle_message(self, srcaddr, msg):

        if msg.kind == 'mih_discovery.response':
            if msg.src in self._peers:
                return

            logging.info('New server found: %s', msg.src)
           
            peer = RemoteMihf(msg.src, srcaddr)
            peer.import_links(msg.payload)

            for link in peer.links:
                logging.info('Remote link found: %s', link)

            self._peers[msg.src] = peer


class ServerMihf(LocalMihf):
    def __init__(self, handler, port=12345):
        super(ServerMihf, self).__init__(handler, port)

    def switch(self, link):
        logging.warning('Attempted to switch MIHF server link.')

    def discover(self, link):
        logging.warning('Attempted to run peer discovery.')

    def run(self):
        logging.info('Starting server MIHF %s', self._name)

        self._make_socket(bind=True)

        while True:
            addr, msg = self._receive()

            if msg:
                self._handle_message(addr, msg)

            ready = self._refresh_links()

            if len(ready) != len(self._links):
                for link in (set(self._links.values()) ^ set(ready)):
                    link.up()


    def _handle_message(self, srcaddr, msg):
        if msg.kind == 'mih_discovery.request':
            if msg.src in self._peers:
                return

            logging.info('New client found: %s', msg.src)
            
            # Server does not care about client links.
            peer = RemoteMihf(msg.src, srcaddr)
            self._peers[msg.src] = peer

            self._send(peer.addr, 'mih_discovery.response', self._export_links(), parent=msg.id)
        
