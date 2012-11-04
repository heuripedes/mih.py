# vim: ts=8 sts=4 sw=4 et nu

import util

# TODO: generate/store message ids for each request
# TODO: store discovery responses

class Message(object):

    def __init__(self, **kw):
        super(Message, self).__init__()

        self.id = util.gen_id('')
        self.parent = kw.pop('parent', None)
        self.kind = kw.pop('kind')
        self.smihf = kw.pop('smihf')
        self.dmihf = kw.pop('dmihf', None)
        self.saddr = kw.pop('saddr', None)
        self.daddr = kw.pop('daddr', None)
        self.payload = kw.pop('payload', None)

    def __repr__(self):
        s = ''
        for k, v in self.__dict__.items():
            if not k.startswith('_'):
                s += '%s=%s, ' % (k, v)

        return 'Message(%s)' % s.rstrip(', ')

    def __getstate__(self):
        dict = self.__dict__.copy()
        for k, v in dict.items():
            if k.startswith('_'):
                del dict[k]

        return dict

    def __setstate__(self, dict):
        self.__dict__.update(dict)


