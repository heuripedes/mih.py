# vim: ts=8 sts=4 sw=4 et ai nu

import collections

MessageBase = collections.namedtuple('Message', 'source, kind, payload')

class Message(MessageBase):
    def __init__(self, source, kind, payload):
        super(self, Message).__init__(source, kind, payload)

