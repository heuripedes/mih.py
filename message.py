
class Message:
    def __init__(self, src, dest, service, operation, action, payload):
        self.src, self.dest = src, dest
        self.service, self.operation, self.action = service, operation, action
        self.payload = payload

    def __str__(self):
        return cPickle.dumps(self)

    @staticmethod
    def request(src, dest, service, action, payload):
        return Message(str(src), str(dest), service, 'request', action, payload)

    @staticmethod
    def response(src, dest, service, action, payload):
        return Message(str(src), str(dest), service, 'response', action, payload)

    @staticmethod
    def indication(src, dest, service, action, payload):
        return Message(str(src), str(dest), service, 'indication', action, payload)

