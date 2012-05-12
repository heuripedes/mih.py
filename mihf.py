# vim: ts=8 sts=4 sw=4 et

import os
import re

def gen_id(name):
    """
    Generates an identifier string.

    The string is formatted as "NR", where N is the provided name and R is a
    hex-encoded randomly generated 32bit number. N is strip()ed and the
    entire string is converted to uppercase.
    """
    
    return (name.strip() + str(os.urandom(4)).encode('hex_codec')).upper()

class MihfEntity(object):
    """
    This class implements the core Media Independent Event Service features.
    """

    def __init__(self):
        self._events = []
        self._subscribers = dict()

    def subscribe(self, event, receiver):
        """Subscribe to the given event(s)"""

        assert event in self._events

        if not obj in self._subscribers[event]:
            self._subscribers[event].append(receiver)

    def _emit(self, event):
        """Triggers an event"""
        
        assert event in self._events

        for subscriber in self._subscribers[event]:
            if not issubclass(subscriber, str):
                method = getattr(subscriber, 'on_' + event)
                method()
            else:
                # TODO: propagate the event remotely
                pass

    def _register_event(self, name):
        """
        Register a new event for this instance.

        name -- the event's name or a list of event names.
        """

        if issubclass(name, list):
            for n in name:
                self._register_event(n)
        else:
            if not name in self._events:
                self._events.append(name)
                self._subscribers[name] = []

class Link(object):
    def __init__(self, ifname, mihf):
        """Constructor"""
        self._ifname = ifname
        self._mihf   = mihf

        self._setup_events()

    def _setup_events(self):
        mies = self._mihf.mies
        mies.register_event('mih_link_down.indication')
        mies.register_event('mih_link_up.indication')

    def activate(self):
        """Activates the interface"""
        
        # TODO: add generic interface activation here
        #raise NotImplemented()

        self._mihf.mies.emit('mih_link_up.indication')

    def deactivate(self):
        """Deactivates the interface"""

        # TODO: add generic interface deactivation here
        #raise NotImplemented()
        
        self._mihf.mies.emit('mih_link_down.indication')

class Link80203(Link):
    def __init__(self, ifname, mihf):
        """Constructor"""
        super(Link80203, self).__init__(ifname, mihf)

class Link80211(Link):
    def __init__(self, ifname, mihf):
        """Constructor"""
        super(Link80211, self).__init__(ifname, mihf)

class Service(object):
    def __init__(self, name):
        """Constructor"""
        self._name = name.strip().upper()
        
        print '- Initializing', self._name, 'service'

# TODO: Find a way to handle remote subscriptions.
class Mies(Service):
    #REQUEST    = 1
    #RESPONSE   = 2
    #INDICATION = 3

    def __init__(self, mihf):
        """Constructor"""
        super(Mies, self).__init__('MIES')

        self._mihf = mihf
        self._subscribers = dict()
        self._handlers = dict()

    def register_event(self, event):
        """Registers an event"""

        if not event in self._subscribers:
            print '- Registering event', event
            self._subscribers[event] = []

    def register_handler(self, handler, name, mihf=None):
        """Registers a handler"""
        if not mihf:
            mihf = self._mihf.id

        handlerstr = mihf + '.' + name
        self._handlers[handlerstr] = handler

    def subscribe(self, event, mihf=None):
        """Subscribe a MIHF to an event"""
       
        # mihf == None means local mihf
        if not mihf:
            mihf = self._mihf 
        
        pair = (handler, mihf)
        
        self._subscribers[event] = handler

    def emit(self, event, data, mihf=None):
        """Notifies the subscribers of the given event"""
        for subscriber in self._subscribers[event]:
            subscriber[0](data)

class Mihf(object):
    def __init__(self):
        """Constructor"""
        
        self._id = gen_id('MIHF-')
       
        print '- Initializing', self._id

        self._init_services()

        self._detect_local_links()
      
    @property
    def id(self):
        return self._id

    @property
    def mies(self):
        return self._mies

    @property
    def mics(self):
        return self._mics
    
    @property
    def miis(self):
        return self._miis
    
    def _init_services(self):
        """Initialize the MIHF services"""

        self._mies = Mies(self)


    def _detect_local_links(self):
        """Reads and parses /proc/net/dev"""
        
        ifnames = []

        with open('/proc/net/dev') as f:
            for line in f:
                if line.count('|') < 1:
                    ifnames.append(line.strip().split(':')[0])

        ifnames.remove('lo') # discard loopback

        self._ifaces = []
        
        print '- Detected interfaces:', ', '.join(ifnames)

        for ifname in ifnames:
            if re.match('^eth', ifname):
                self._ifaces.append(Link80203(ifname, self))
            elif re.match('^wlan', ifname):
                self._ifaces.append(Link80211(ifname, self))

        print self._ifaces



def on_mih_link_down_indication(data):
    print "link down!"

if __name__ == '__main__':
    f = Mihf()


