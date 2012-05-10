#vim: sts=4 ts=4 sw=4 et

import mihp

class Miis(mihp.Service):
    def __init__(self):
        super(Miis, self).__init__(name='MIIS')

