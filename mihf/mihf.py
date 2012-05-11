# vim: sts=4 ts=8 sw=4 et

import util

class Mihf:
    def __init__(self, addr="0.0.0.0", port="1234"):
        """Constructor"""
        self._services = dict()
        self._peers = []
        self._addr  = addr
        self._port  = port

        self._id = util.gen_id("MIHF")

    def add_service(self, service):
        """Add a new service to this MIHF"""
        service.set_mihf(self)
        self._services[service.name] = service;

    def add_peer(self, peer):
        """Add a peer MIHF"""
        self._peers.append(peer)
    
    def run(self):
        """Run the MIHF"""
        pass

