# vim: ts=8 sts=4 sw=4 et ai nu

import util
import cPickle
import pickletools

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

    def __getstate__(self):
        return self.__dict__

    def __repr__(self):
        return 'Message(id=%s, parent=%s, kind=%s, src=%s, dst=%s, payload=%s)'\
                % (self.id, self.parent, self.kind, self.src, self.dst, self.payload)

    def pickle(self):
        return pickletools.optimize(cPickle.dumps(self))

    @staticmethod
    def unpickle(pickledmsg):
        return cPickle.loads(pickledmsg)

    #def __getitem__(self, key):
    #    keys = ['id', 'parent', 'kind', 'src', 'dst', 'payload']
    #    return getattr(self, keys[key])

