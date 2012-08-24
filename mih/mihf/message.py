# vim: ts=8 sts=4 sw=4 et ai nu

import util

# TODO: generate/store message ids for each request
# TODO: store discovery responses

class Message(object):

    def __init__(self, src, kind, payload=None, dst=None, parent=None):
        super(Message, self).__init__()

        self.id = util.gen_id('')
        self.parent = parent
        self.kind = kind
        self.src = src
        self.dst = dst
        self.payload = payload

    def __repr__(self):
        return 'Message(id=%s, parent=%s, kind=%s, src=%s, dst=%s, payload=%s)'\
                % (self.id, self.parent, self.kind, self.src, self.dst, self.payload)

    def __getstate__(self):
        dict = self.__dict__.copy()
        for k, v in dict.items():
            if k.startswith('_'):
                del dict[k]

        return dict

    def __setstate__(self, dict):
        self.__dict__.update(dict)



    #def __getitem__(self, key):
    #    keys = ['id', 'parent', 'kind', 'src', 'dst', 'payload']
    #    return getattr(self, keys[key])

