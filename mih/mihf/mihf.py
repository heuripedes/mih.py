# vim: ts=8 sts=4 sw=4 et nu

import time
import socket
import select
import logging 
import errno

import collections

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
    def __init__(self, handler, port=12345, peek_time=10, msg_size=8192, max_recv=10):
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
        self._msg_size = 4096
        self._max_recv = max_recv

        self._next_refresh = time.time()-1
        self._ready_cache  = list()

        self._oqueue = collections.deque()
        self._iqueue = collections.deque()

    @property
    def current_link(self):
        return self._curlink

    def discover(self, link):

        if not isinstance(link, str):
            link = link.ifname

        util.bind_sock_to_device(self._sock, link)
    
        self._send(None, 'mih_discovery.request', daddr=('<broadcast>', self._port))

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

        # XXX: using select() with blocking sockets lowers the CPU usage for
        #      some reason.

        #self._sock.setblocking(blocking)
        self._sock.settimeout(timeout)

    def _send(self, dmihf, kind, payload=None, parent=None, daddr=None, link=None):
        """Put a message on the output queue."""

        assert daddr or (not daddr and dmihf)

        if not daddr:
            daddr = self._peers[dmihf]

        msg = Message(
                smihf=self._name, dmihf=dmihf,
                kind=kind, payload=payload, parent=parent,
                daddr=daddr
                )

        self._oqueue.append((link, msg))

    def _receive(self):
        while self._iqueue:
            yield self._iqueue.pop()

    def _flush_buffer(self):
        """Flushes the output queue into the socket."""

        while self._oqueue:
            link, msg = self._oqueue.pop()

            if link:
                util.bind_sock_to_device(self._sock, link)

            sent = 0
            attempts = 4
            
            while not sent and attempts:
                try: 
                    data = util.pickle(msg).ljust(self._msg_size, '\x00')
                    sent += self._sock.sendto(data, 0, msg.daddr)

                except socket.timeout:
                    attempts -= 1
                    pass

            if not attempts:
                logging.warning('Failed to send message to %s: too many timeouts', msg.daddr)
            
            if link:
                util.bind_sock_to_device(self._sock, '')


    def _fill_buffer(self):
        """Fills the input queue."""

        count = self._max_recv

        while count:
            
            data, addr = '', (None, None)

            try:
                data, addr = self._sock.recvfrom(self._msg_size)
            except socket.timeout:
                break

            data = data.rstrip('\x00')
            
            if data:
                msg = util.unpickle(data)
                count -= 1

            self._iqueue.append((addr, msg))


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
        """Refreshes the MIHF link list."""
       
        if self._next_refresh < time.time():
            self._next_refresh = time.time() + 0.5 # 500 ms
        else:
            return self._ready_cache

        llnames = get_local_ifnames()
        new  = list(set(llnames) - set(self._links.keys()))
        dead = list(set(self._links.keys()) - set(llnames))

        for name in dead:
            # NOTE: send link down?
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
            self._peek_links()
            self._next_peek += self._peek_time

        self._ready_cache = ready

        return ready

    def _peek_links(self):
        wifi = filter(lambda link: link.wifi, g.links)

        for name, link in wifi.items():
            if not link.up():
                link.down()

    def _proccess_messages(self):
        #addr, msg = self._receive()
        #if msg:
        #    self._handle_message(addr, msg)
            
        for addr, msg in self._receive():
            self._handle_message(addr, msg)



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
            self._fill_buffer()
            self._proccess_messages()

            ready = self._refresh_links()

            if not ready:
                for link in self._links.values():
                    if self.switch(link):
                        break

            self._flush_buffer()


    def _handle_message(self, srcaddr, msg):
        
        if msg.kind == 'mih_discovery.response':
            if msg.smihf in self._peers:
                return

            logging.info('New server found: %s', msg.smihf)
           
            peer = RemoteMihf(msg.smihf, srcaddr)
            peer.import_links(msg.payload)

            for link in peer.links:
                logging.info('Remote link found: %s', link)

            self._peers[msg.smihf] = peer


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
            self._fill_buffer()
            self._proccess_messages()

            ready = self._refresh_links()

            if len(ready) != len(self._links):
                for link in (set(self._links.values()) ^ set(ready)):
                    link.up()

            self._flush_buffer()


    def _handle_message(self, srcaddr, msg):
        
        if msg.kind == 'mih_discovery.request':
            if msg.smihf not in self._peers:
                logging.info('New client found: %s', msg.smihf)
                self._peers[msg.smihf] = RemoteMihf(msg.smihf, srcaddr)
            
            # Server does not care about client links.
            
            self._send(msg.smihf, 'mih_discovery.response',
                    self._export_links(), parent=msg.id, daddr=srcaddr)

        
