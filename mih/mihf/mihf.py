# vim: ts=8 sts=4 sw=4 et nu

import time
import socket
import logging

import collections

import mih.mihf.util as util
from mih.mihf.link import get_local_ifnames
from mih.mihf.link import make_link
from mih.mihf.link import Link
from mih.mihf.messagemanager import MessageManager

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

        self._msgmngr = MessageManager()

        # event queue
        self._equeue = list() #collections.deque()

    def discover(self, link):

        if not link.discoverable:
            return

        if not isinstance(link, str):
            link = link.ifname

        self._send(None, 'mih_discovery.request', daddr=('<broadcast>', self.PORT), link=link)

    def switch(self, link):
        success = False

        # same link, try to reconnect
        if self.current_link == link:
            success = link.is_ready() or link.up()

            if success:
                link.route_up()
                logging.info('Link %s reestablished.', link)
            else:
                logging.info('Failed to reestablish %s link.', link)

            return success
 
        # start the handover

        ho_origin = self.current_link
        ho_begin = time.time()

        logging.info('Handover from %s to %s started.', ho_origin, link)

        success = link.is_ready() or link.up()

        if success:
            if self.current_link:
                self.current_link.down()

            link.route_up() # replaces the old route.

            self.current_link = link

            if link.is_mobile():
                self._next_peek = time.time() + self.PEEK_TIME
        else:
            link.down()

        ho_time = time.time() - ho_begin
        ho_status = 'successfully' if success else 'unsuccessfully'

        logging.info('Handover from %s to %s finished %s in %is',
            ho_origin, link, ho_status, ho_time)

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

        self._msgmngr.send(
                self.name,
                daddr,
                kind,
                dmihf=dmihf,
                payload=payload,
                parent=parent,
                link=link)

    def _handle_message(self, srcaddr, msg):
        pass

    def _handle_link_event(self, link, state):
        # replace previous events on the link
        for i in xrange(0, len(self._equeue)):
            if self._equeue and self._equeue[i][0] == link:
                del self._equeue[i]

        self._equeue.append((link, state))

    def _export_links(self):
        """Returns a list of link data suitable for remote use."""

        exported = []

        for link in self.links.values():
            dic = link.as_dict()
            dic['remote'] = True

            exported.append(dic)

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
            logging.info('Found link %s.', name)
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
        """Check if there are non-mobile links available.

        When the current link is a mobile one, this method is called
        every PEEK_TIME seconds to check if there are available links on
        in the environment."""

        # XXX: what is cheaper?
        #      (a) enable + disable (on failure)
        #      (b) keep it enabled and just check to see if it is ready?

        logging.debug('Peeking links')
        wifi = [link for link in self.links.values() if not link.is_mobile()]

        for link in wifi:
            is_up = link.up()
            if not is_up or (is_up and util.link_compare(link, self.current_link) < 1):
                link.down()

    def _proccess_messages(self):
        for addr, msg in self._msgmngr.receive():
            self._handle_message(addr, msg)

    def _process_events(self):
        """Processes the event queue.

        This method iterates through the event queue and calls the
        respective event handles, when found.
        
        The event queue is cleared."""

        events = list(self._equeue)
        self._equeue = list()
        
        for link, state in events:
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

        self._make_socket()
        self._scan_links()

        logging.info('Client MIHF %s started.', self.name)

        while True:
            self._msgmngr.fill_queue(self._sock)
            self._proccess_messages()

            ready = self._refresh_links()

            if not ready:
                logging.warning('No ready link found, trying to bring one up')
                for link in self.links.values():
                    if self.switch(link):
                        break

            self._process_events()

            self._msgmngr.flush_queue(self._sock)

    def report(self):

        if not self._peers:
            logging.debug('There is no one to ask a report from.')
            return False

        # Broadcast to the known servers
        for peer in self._peers:
            links = self._peers[peer].links.keys()
            self._send(peer, 'mih_report.request', payload=links)

        return True

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
                logging.debug('Ignoring report from %s.', msg.smihf)
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

        self._make_socket(bind=True)
        self._scan_links()

        logging.info('Server MIHF %s started.', self.name)

        while True:
            self._msgmngr.fill_queue(self._sock)
            self._proccess_messages()

            ready = self._refresh_links()

            if len(ready) != len(self.links):
                for link in (set(self.links.values()) ^ set(ready)):
                    link.up()

            self._process_events()

            self._msgmngr.flush_queue(self._sock)

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

