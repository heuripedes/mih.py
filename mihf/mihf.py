#vim: sts=4 ts=4 sw=4 et

import mics
import mies
import miis

class Mihf(object):
    def __init__(self):
        super(Mihf, self).__init__()
        
        self._services = dict()
   
        services = [miis.Miis(), mies.Mies(), mics.Mics()]
        self._miis, self._mies, self._mics = services

        for s in services:
            self._add_service(s)
        
    def run(self):
        """ Runs the MIHF. """
        pass
    
    def _add_service(self, service):
        """ Add a service to this MIHF. """
        self._services[service.name] = service

