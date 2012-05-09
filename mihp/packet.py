import struct

class Packet(object):
	def __init__(self, **kwargs):
		super(Packet, self).__init__()
		self.service   = kwargs.get('service')
		self.operation = kwargs.get('operation')
		self.payload   = kwargs.get('payload')

	def to_struct(self):
		raise NotImplementedError()





