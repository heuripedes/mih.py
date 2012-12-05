# vim: ts=8 sts=4 sw=4 et nu

import mih.mihf.util as util

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
        buf = ''
        for key, value in self.__dict__.items():
            if not key.startswith('_'):
                buf += '%s=%s, ' % (key, value)

        return 'Message(%s)' % buf.rstrip(', ')

    def __getstate__(self):
        dic = self.__dict__.copy()
        for key in dic.keys():
            if key.startswith('_'):
                del dic[key]

        return dic

    def __setstate__(self, dic):
        self.__dict__.update(dic)
