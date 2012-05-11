# vim: sts=4 ts=8 sw=4 et

import util

class Service:
    def __init__(self, name):
        """Constructor."""
        self._name = name.strip().upper()
        self._mihf = None
        self._id   = util.gen_id(name)

    @property
    def name(self):
        """The name of the service."""
        return self._name

    def set_mihf(self, mihf):
        """Set the MIHF this service is attached to (only once)."""
        assert self._mihf == None

        self._mihf = mihf

