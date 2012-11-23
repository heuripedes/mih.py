# vim: ts=8 sts=4 sw=4 et nu

import time
import socket
import logging

import collections

import mih.mihf.util as util
#from mih.mihf.link import *
from mih.mihf.link import get_local_ifnames
from mih.mihf.link import make_link
from mih.mihf.link import Link

from mih.mihf.message import Message


class BasicMihf(object):
    """This class describes the common operations that all MIHFs classes
    should implement"""

    def __init__(self):
        pass

    # MIH Commands
    def discover(self, link):
        """Broadcasts a server discovery request through *link*. *link*
        can either be a Link instance or a string containing the interface
        name."""
        raise NotImplementedError

    def switch(self, link):
        """Switches to the link described by *link*."""
        raise NotImplementedError

    def report(self):
        """Return information about the links in *links*."""
        raise NotImplementedError


class LocalMihf(BasicMihf):
    MSG_SIZE = 4096
    MAX_RECV = 10
    PEEK_TIME = 10
    PORT = 12345

    def __init__(self, handler):
        super(LocalMihf, self).__init__()

        self.name = util.gen_id('MIHF-')

        self.links = dict()
        self.current_link = None

        self._sock = None

        self._peers = dict()
        self._handler = handler

        self._next_peek = time.time()
        self._next_refresh = time.time() - 1

        self._ready_cache = list()

        self._oqueue = collections.deque()
        self._iqueue = collections.deque()

        # event queue
        self._equeue = collections.deque()

    def discover(self, link):

        if not link.discoverable:
            return

        if not isinstance(link, str):
            link = link.ifname

        self._send(None, 'mih_discovery.request', daddr=('<broadcast>', self.PORT), link=link)

    def switch(self, link):

        logging.debug('Switching from %s to %s...', self.current_link, link)

        success = False
        ho_begin = time.clock()  # handover begin
        ho_from = self.current_link
        ho_to = link

        if link.is_ready():
            success = True
        else:
            if not link.up():
                link.down()
                success = False

        if success:
            if self.current_link:
                self.current_link.down()

            self.current_link = link

            if link.is_mobile():
                self._next_peek = time.time() + self.PEEK_TIME

        ho_time = time.clock() - ho_begin
        ho_status = 'successfully' if success else 'unsuccessfully'

        logging.info('Handover from %s to %s finished %s in %.2fs',
            ho_from, ho_to, ho_status, ho_time)

        return success

    def _make_socket(self, bind=False, blocking=True, timeout=0.3):

        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        if bind:
            self._sock.bind(('', self.PORT))

        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, True)

        # XXX: using select() with blocking sockets lowers the CPU usage for
        #      some reason.

        self._sock.setblocking(blocking)
        self._sock.settimeout(timeout)

    def _send(self, dmihf, kind, payload=None, parent=None, daddr=None, link=None):
        """Put a message on the output queue."""

        assert daddr or (not daddr and dmihf)

        if not daddr:
            daddr = self._peers[dmihf].addr

        msg = Message(
                smihf=self.name, dmihf=dmihf,
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

            logging.debug("Sending %s to %s", msg.kind, msg.daddr)

            sent = 0
            attempts = 4

            while not sent and attempts:
                try:
                    data = util.pickle(msg).ljust(self.MSG_SIZE, '\x00')
                    sent += self._sock.sendto(data, 0, msg.daddr)

                except socket.timeout:
                    attempts -= 1

            if not attempts:
                logging.warning('Failed to send message to %s: too many timeouts', msg.daddr)

            if link:
                util.bind_sock_to_device(self._sock, '')

    def _fill_buffer(self):
        """Fills the input queue."""

        count = self.MAX_RECV

        while count:
            data, addr = '', (None, None)

            try:
                data, addr = self._sock.recvfrom(self.MSG_SIZE)
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
        self._equeue.append((link, state))

    def _export_links(self):
        """Returns a list of link data suitable for remote use."""

        exported = []

        for link in self.links.values():
            d = link.as_dict()
            d['remote'] = True

            exported.append(d)

        return exported

    def _scan_links(self):
        """Checks for newly added interfaces and removes nonexistent ones."""

        llnames = get_local_ifnames()
        new = list(set(llnames) - set(self.links.keys()))
        dead = list(set(self.links.keys()) - set(llnames))

        for name in dead:
            # XXX: send link down?
            logging.warning('Local link not found %s', name)
            del self.links[name]

        for name in new:
            logging.debug('Found link %s.', name)
            link = make_link(ifname=name)
            link.on_link_event = self._handle_link_event
            self.links[name] = link

    def _refresh_links(self):
        """Refreshes the MIHF link list."""

        if self._next_refresh < time.time():
            self._next_refresh = time.time() + 0.5  # 500 ms
        else:
            return self._ready_cache

        ready = []

        for link in self.links.values():
            link.poll_and_notify()

            if link.is_ready():
                ready.append(link)

        on_mobile = self.current_link and self.current_link.is_mobile()

        if on_mobile and time.time() > self._next_peek:
            self._peek_links()
            self._next_peek += self.PEEK_TIME

        self._ready_cache = ready

        return ready

    def _peek_links(self):
        wifi = filter(lambda link: link.is_wifi(), self.links)

        for link in wifi.values():
            if not link.up():
                link.down()

    def _proccess_messages(self):
        for addr, msg in self._receive():
            self._handle_message(addr, msg)

    def _process_events(self):
        while self._equeue:
            link, state = self._equeue.pop()

            logging.info('Link %s is %s', link, state)

            if self._handler:
                fname = 'link_' + state.replace(' ', '_')

                if hasattr(self._handler, fname):
                    getattr(self._handler, fname)(self, link)


class RemoteMihf(BasicMihf):

    def __init__(self, name, addr):
        super(RemoteMihf, self).__init__()

        self.addr = addr
        self.name = name
        self.links = dict()

    def import_links(self, links):
        for link in links:
            self.links[link['ifname']] = Link(**link)


class ClientMihf(LocalMihf):

    def __init__(self, handler):
        super(ClientMihf, self).__init__(handler)

        self.last_report = None

    def run(self):
        logging.info('Starting client MIHF %s', self.name)

        self._make_socket()
        self._scan_links()

        while True:
            self._fill_buffer()
            self._proccess_messages()

            ready = self._refresh_links()

            if not ready:
                for link in self.links.values():
                    if self.switch(link):
                        break

            self._process_events()

            self._flush_buffer()

    def report(self):

        # Broadcast to the known servers
        for peer in self._peers:
            links = self._peers[peer].links.keys()
            self._send(peer, 'mih_report.request', payload=links)

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

        if msg.kind == 'mih_report.response':
            if msg.smihf not in self._peers:
                return

            logging.info('Received report from %s.', msg.smihf)

            if self.last_report:
                logging.info('Ignoring report from %s.', msg.smihf)
                return

            peer = self._peers[msg.smihf]
            peer.import_links(msg.payload)

            links = []
            for link in msg.payload:
                links += [Link(**link)]

            self.last_report = links


class ServerMihf(LocalMihf):

    def __init__(self, handler):
        super(ServerMihf, self).__init__(handler)

    def switch(self, link):
        logging.warning('Attempted to switch MIHF server link.')

    def discover(self, link):
        logging.warning('Attempted to run peer discovery.')

    def run(self):
        logging.info('Starting server MIHF %s', self.name)

        self._make_socket(bind=True)
        self._scan_links()

        while True:
            self._fill_buffer()
            self._proccess_messages()

            ready = self._refresh_links()

            if len(ready) != len(self.links):
                for link in (set(self.links.values()) ^ set(ready)):
                    link.up()

            self._process_events()

            self._flush_buffer()

    def _handle_message(self, srcaddr, msg):

        if msg.kind == 'mih_discovery.request':
            if msg.smihf not in self._peers:
                logging.info('New client found: %s', msg.smihf)
                self._peers[msg.smihf] = RemoteMihf(msg.smihf, srcaddr)

            # Server does not care about client links.

            self._send(msg.smihf, 'mih_discovery.response',
                    self._export_links(), parent=msg.id, daddr=srcaddr)

        if msg.kind == 'mih_report.request':
            self._send(msg.smihf, 'mih_report.response',
                    self._export_links(), parent=msg.id, daddr=srcaddr)
