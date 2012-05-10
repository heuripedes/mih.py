#vim: sts=4 ts=4 sw=4 et

class Service(object):
    def __init__(self, name):
        super(Service, self).__init__()

        self._name = name.upper().strip()

    @property
    def name(self):
        return self._name

    def on_receive(self, mihp):
        raise NotImplementedError()

