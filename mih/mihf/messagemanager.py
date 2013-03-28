# vim: ts=8 sts=4 sw=4 et nu

import collections
import socket
import logging
from mih.mihf import util
from mih.mihf.message import Message

class MessageManager(object):
    """Class to manage the input and output message queues for the MIHF"""

    def __init__(self, msgsize=4096, maxrecv=10, maxattempts=4):
        super(MessageManager, self).__init__()

        assert msgsize > 0
        assert maxrecv > 0
        assert maxattempts > 0

        self.msgsize = msgsize
        self.maxrecv = maxrecv
        self.maxattempts = maxattempts

        self.iqueue  = collections.deque()
        self.oqueue  = collections.deque()

    def fill_queue(self, sock):
        """Fills the input queue.

        `sock` is expected to be a nonblocking socket."""

        assert sock

        for _ in range(0, self.maxrecv):
            data, addr = '', (None, None)

            try:
                while not data:
                    data, addr = sock.recvfrom(self.msgsize)
                    data = data.rstrip('\x00')

            except socket.timeout:
                break

            else:
                self.iqueue.append((addr, util.unpickle(data)))

    
    def flush_queue(self, sock):
        """Flushes the output queue into the socket."""

        assert sock

        while self.oqueue:
            link, msg = self.oqueue.pop()

            util.bind_sock_to_device(sock, link or '')

            logging.debug("Sending %s to %s", msg.kind, msg.daddr)

            sent = 0
            data = util.pickle(msg).ljust(self.msgsize, '\x00')

            for _ in range(0, self.maxattempts):
                try:
                    sent += sock.sendto(data[sent:], 0, msg.daddr)
                except socket.timeout:
                    continue

            if sent != len(data):
                logging.warning('Failed to send message to %s: too many timeouts.', msg.daddr)

            util.bind_sock_to_device(sock, link or '')

    def receive(self):
        """Generator for the input message queue.
        
        The messages are `pop()`ed out of the queue."""

        while self.iqueue:
            yield self.iqueue.pop()

    def send(self, smihf, daddr, kind, dmihf=None, payload=None, parent=None, link=None):
        """Put a message on the output queue. """
        
        assert smihf
        assert daddr
        assert kind

        msg = Message(
                smihf=smihf,
                dmihf=dmihf,
                daddr=daddr,
                kind=kind,
                payload=payload,
                parent=parent
                )

        self.oqueue.append((link, msg))

