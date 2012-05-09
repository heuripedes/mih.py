
class Mihf(object):
	def __init__(self):
		super(Mihf, self).__init__()

		self.services = dict()
	
	def add_service(self, service):
		"""
		Add a service to this MIHF.
		"""

		self.services[service.name] = service
	
	def run(self):
		"""
		Runs the MIHF.
		"""
		pass
