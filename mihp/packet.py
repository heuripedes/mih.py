#vim: sts=4 ts=4 sw=4 et
import struct

class Packet(object):
    def __init__(self, **kwargs):
        super(Packet, self).__init__()
        self.service   = kwargs.get('service')
        self.operation = kwargs.get('operation')
        self.payload   = kwargs.get('payload')

    def to_string(self):
        raise NotImplementedError()





