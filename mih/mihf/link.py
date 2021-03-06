# vim: ts=8 sts=4 sw=4 et nu

import collections
import errno
import subprocess as subproc
import re
import time
import dbus
import logging
from threading import Thread

import sockios
sockios.init()

import mih.mihf.util as util
import mih.mihf.mm as mm

# Interface properties

# Wired
WIRED_UP_STRENGHT = 1000
WIRED_DOWN_STRENGHT = 0

# Wifi
WIFI_ESSID = 'GREDES_MIH'
WIFI_KEY = ''
#WIFI_THRESHOLD = 37
WIFI_THRESHOLD = 45
WIFI_SAMPLES = 10
WIFI_MODE = 'managed'
WIFI_CHANNEL = 6

# Mobile
MOBILE_GSM_NUMBER = '*99#'
MOBILE_GSM_APN = 'gprs.oi.com.br'
#MOBILE_GSM_USER = 'oi'
#MOBILE_GSM_PASS = 'oi'
MOBILE_GSM_USER = ''
#MOBILE_GSM_PASS = 'oioioi'
MOBILE_GSM_PASS = ''

def filter_invalid_ifnames():
    ifnames = sockios.get_iflist()

    for ifname in ifnames:
        # skip bridges
        if re.search(r'(br\d+$|^tun|^tap)', ifname):
            continue

        # skip local, virtual, ppp and monitoring interfaces
        if re.search(r'^(lo|vbox|vir|ppp|mon)', ifname):
            continue

        yield ifname

def get_local_ifnames():
    """
    Looks for links in /proc/net/dev
    """

    ifnames = list(filter_invalid_ifnames())
    ifnames += mm.ModemManager.EnumerateDevices()

    return ifnames


def make_link(**kwargs):
    if kwargs.get('remote', False):
        tech = kwargs.get('technology')
        if tech == 'wired':
            return Link80203(**kwargs)
        elif tech == 'wifi':
            return Link80211(**kwargs)
        elif tech == 'mobile':
            return LinkMobile(**kwargs)

    ifname = kwargs.get('ifname')
    if ifname.startswith('/'):
        return LinkMobile(**kwargs)

    try:
        output = subproc.check_output(['iwconfig', ifname],
            stderr=open('/dev/null'))

        if re.findall('IEEE 802.11', output):
            return Link80211(**kwargs)
    except subproc.CalledProcessError:
        pass

    return Link80203(**kwargs)


class Link(object):
    """Base class for links."""

    def __init__(self, **kwargs):

        self.ifname = None
        self.ipaddr = ''
        self.routeopts = []
        self.state = None  # force link_up on first poll()
        self.remote = False
        self.ready = False
        self.discoverable = True
        self.technology = getattr(self, 'technology', 'unknown')

        self.on_link_event = lambda (a, b): None  # callbacks

        self.update(**kwargs)

        #self.poll()

    def is_wifi(self):
        """Is this link a WiFi link?"""
        return self.technology == 'wifi'

    def is_mobile(self):
        """Is this link a mobile link?"""
        return self.technology == 'mobile'

    def is_wired(self):
        """Is this link a wired link?"""
        return self.technology == 'wired'

    def __repr__(self):
        return '%s(name=%s, ipv4=%s)' % \
                (self.__class__.__name__, self.ifname, self.ipaddr)

    def update(self, **kwargs):
        """Updates the link object state."""
        vars(self).update(kwargs)

        if self.remote and hasattr(self, 'ready'):
            self._ready = self.ready
            del self.ready
        else:
            self._poll_ifconf()

    def _poll_ifconf(self):
        """Refreshes the link's IPv4 and MAC addresses."""
        ifconf = None
        try:
            ifconf = sockios.get_ifconf(self.ifname)
            self.ipaddr = ifconf['in_addr'] or ''
        except sockios.error:
            self.ipaddr = ''

        assert self.ipaddr != '127.0.0.1'

    def poll(self):
        """Refreshes the link object's state."""
        assert not self.remote

        if not self.ifname:
            return

        self.state = sockios.is_up(self.ifname)

        if self.state:
            self._poll_ifconf()
        else:
            self.ipaddr = ''

        if self.ifname and not self.routeopts:
            self.routeopts = util.get_defroute_opts(self.ifname)

    def poll_and_notify(self):
        """Refreshes the internal state and notifies users of link events."""
        assert not self.remote

        before = self.state

        self.poll()

        is_ready = self.state

        if before != is_ready:
            self.on_link_event(self, 'up' if is_ready else 'down')

    def up(self):
        """Set's the link's interface up."""
        assert not self.remote

        if not self.state:
            sockios.set_up(self.ifname)
            time.sleep(0.1)
            self.state = sockios.is_up(self.ifname)

        return self.state

    def down(self):
        """Set's the link's interface down."""
        assert not self.remote

        if self.state:
            if self.is_ready():
                util.dhcp_release(self.ifname)

                subproc.call(['ip', 'addr', 'flush', 'dev', self.ifname])

                self.route_down()

                sockios.set_down(self.ifname)

                #if not self.state:
                #    self.on_link_event(self, 'down')

            elif self.ifname:
                self.route_down()
                sockios.set_down(self.ifname)

            self.poll()
            self.ipaddr = ''

        return not self.state

    def route_up(self):
        """Activates the interfaces's default route"""
        if self.routeopts and self.ifname:
            logging.debug('Activating %s default route', self.ifname)
            subproc.call(['ip', 'route', 'add'] + self.routeopts)

    def route_down(self):
        """Deactivates the interfaces's default route"""
        if self.ifname:
            logging.debug('Deactivating %s default route', self.ifname)
            subproc.call(['ip', 'route', 'del', 'default', 'dev', self.ifname])

    def is_ready(self):
        """Checks whether the link is ready."""

        if getattr(self, '_ready', False):
            return True

        if self.state and len(self.ipaddr) > 0:
            return True

        return False

    def as_dict(self):
        """Returns the link's internal state as a dict()."""
        dic = {}
        for key, val in self.__dict__.items():
            if key[0] == '_':
                continue

            if isinstance(val, dbus.String):
                val = val.encode('utf-8')
            elif isinstance(val, dbus.UInt32):
                val = int(val)

            dic[key] = val

        if self.remote and hasattr(self, '_ready'):
            dic['ready'] = getattr(self, '_ready')

        del dic['on_link_event']

        return dic


class Link80203(Link):

    def __init__(self, **kwargs):
        self.technology = 'wired'
        self.strenght = 0

        super(Link80203, self).__init__(**kwargs)

    def update(self, *args, **kwargs):
        super(Link80203, self).update(*args, **kwargs)

    def poll(self):
        super(Link80203, self).poll()

        if not self.remote:
            try:
                self.state = self.state and sockios.is_running(self.ifname)
            except OSError, e:
                # something happened, the interface might be down
                self.state = False

        if self.state and self.ipaddr:
            self.strenght = WIRED_UP_STRENGHT
        else:
            self.strenght = WIRED_DOWN_STRENGHT

    def up(self):
        if self.is_ready():
            return True

        if not super(Link80203, self).up():
            return False

        # cable not connected
        if not sockios.is_running(self.ifname):
            return False

        util.dhcp_release(self.ifname)
        util.dhcp_renew(self.ifname)

        self.routeopts = util.get_defroute_opts(self.ifname)

        self.poll()

        self.route_up()

        #if self.is_ready():
        #    self.on_link_event(self, 'up')

        return self.is_ready()


class Link80211(Link):
    def __init__(self, **kwargs):
        self.technology = 'wifi'
        self.strenght = 0
        self.samples = None
        self.essid = None
        self.mode = 'managed'

        super(Link80211, self).__init__(**kwargs)

    def update(self, **kwargs):
        super(Link80211, self).update(**kwargs)

        if not self.remote:
            # Reset sampling
            self.strenght = 0
            self.samples = collections.deque(maxlen=WIFI_SAMPLES)

            output = subproc.check_output(['iwconfig', self.ifname])
            self.mode = re.findall(r'Mode:(\w+)', output)[0].lower()

    def poll(self):
        super(Link80211, self).poll()

        if self.mode == 'master':
            return

        if self.state and util.match_output('Not-Associated', ['iwconfig', self.ifname]):
            self.state = False

        # Collect signal strenght samples
        if self.is_ready():
            try:
                with open('/sys/class/net/' + self.ifname + '/wireless/link') as f:
                    self.strenght = int(f.readline().strip())
                    self.samples.append(self.strenght)

                output = subproc.check_output(['iwconfig', self.ifname])
                matches = re.findall('ESSID:"([^"$]+)', output)
                self.essid = matches[0].strip()
            except Exception, e:
                logging.warning('Failed to query signal strenght: %s', e)

        else:
            self.strenght = 0
            self.samples.clear()
            self.essid = None

    def poll_and_notify(self):
        super(Link80211, self).poll_and_notify()

        if self.state and self.is_going_down():
            self.on_link_event(self, 'going down')

    def up(self):
        assert not self.remote

        if self.is_ready():
            return True

        subproc.call(['rfkill', 'unblock', 'all'])

        if not super(Link80211, self).up():
            return False

        essid = WIFI_ESSID
        #key = WIFI_KEY

        cmd = ['iwconfig', self.ifname, 'essid', essid]

        #if key:
        #    cmd += ['key', key]

        #cmd += ['mode', WIFI_MODE]
        #cmd += ['channel', str(WIFI_CHANNEL)]

        if subproc.call(cmd) != 0:
            return False

        time.sleep(0.2)

        if util.match_output('Not-Associated', ['iwconfig', self.ifname]):
            #logging.warning('Failed to associate %s to %s', self.ifname, essid)
            return False

        util.dhcp_release(self.ifname)
        util.dhcp_renew(self.ifname)

        self.routeopts = util.get_defroute_opts(self.ifname)

        self.poll()

        self.route_up()

        if self.is_ready():
            self.on_link_event(self, 'up')

        return self.is_ready()

    def is_going_down(self):
        #return (len(self.samples) == WIFI_SAMPLES and
        #        util.average(self.samples) < WIFI_THRESHOLD)
        return util.average(self.samples) < WIFI_THRESHOLD


# XXX: based on https://github.com/openshine/ModemManager/blob/master/test/mm-test.py
class LinkMobile(Link):

    def __init__(self, **kwargs):

        self.discoverable = False
        self.technology = 'mobile'
        self.strenght = 0
        self.samples = None
        self._pppd = None

        if not kwargs.get('remote'):

            self._modem = mm.Modem(kwargs.get('ifname'))

            if self._modem.Type != mm.MM_MODEM_TYPE_GSM:
                raise Exception('Unsupported modem type.')

            self._dbus_name = kwargs.get('ifname')

            self.m_master = self._modem.MasterDevice
            self.m_device = self._modem.Device

            kwargs['ifname'] = None

            if self._modem.State == mm.MM_MODEM_STATE_CONNECTED:
                self._detect_iface()

        # TODO: try to restore a previous session
        if 'ppp10' in sockios.get_iflist():
            self.ifname = 'ppp10'

        super(LinkMobile, self).__init__(**kwargs)

    def update(self, *args, **kwargs):
        super(LinkMobile, self).update(*args, **kwargs)

        self.ipaddr = ''
        self.strenght = 0
        self.samples = collections.deque(maxlen=WIFI_SAMPLES)

        if self.remote:
            self.strenght = kwargs.pop('strenght', -1)

    def _poll_ifconf(self):
        if self.ifname:
            super(LinkMobile, self)._poll_ifconf()

    def poll(self):
        if self.remote:
            return

        self.state = (self._modem.State == mm.MM_MODEM_STATE_CONNECTED)

        if not self.state:
            return

        status = None
        try:
            status = self._modem.GetStatus()
        except dbus.DBusException:
            pass

        if not self.is_ready():
            self.strenght = 0
            self.samples.clear()
        elif self.is_ready() and status:
            self.strenght = int(status['signal_quality'])
            self.samples.append(self.strenght)

        super(LinkMobile, self).poll()


    def poll_and_notify(self):
        oldstate = self.is_ready()
        try:
            super(LinkMobile, self).poll_and_notify()
        except sockios.error, e:
            if e.errno == errno.ENODEV and oldstate:
                self.ifname = ''
                self.on_link_event(self, 'down')

    def _detect_iface(self):
        pass

    def _enable(self, enable):
        logstr = 'Enabling' if enable else 'Disabling'
        logging.debug('%s modem...', logstr)

        try:
            self._modem.Enable(enable)
            return True
        except dbus.DBusException, e:
            logstr = 'enable' if enable else 'disable'
            logging.debug('Failed to %s the modem: %s', logstr, str(e))

            return False

    def _pppd_connect(self):  # osi data link layer (ppp)
        args = [
                '/usr/sbin/pppd',  # command
                'nodetach', 'lock', 'nodefaultroute', 'noipdefault',
                'noauth', 'crtscts', 'modem', 'usepeerdns',
                'unit', '10',  # ppp10
                #'debug',
                '115200'  # baud
                ]

        if MOBILE_GSM_USER:
            args += ['user', MOBILE_GSM_USER]

        args += [self.m_device]

        logging.debug('Dialing...')

        try:
            # XXX: pppd output must be unbufered or read()/write() will block.
            # in case pppd stdout is buffered, use UNIX sockets using
            # socket.socketpair()
            self._pppd = subproc.Popen(args, cwd='/', env={},
                    stdout=subproc.PIPE, stderr=subproc.PIPE)
        except IOError, e:
            if e.errno == errno.ENOENT:
                logging.critical('pppd executable not found.')
            else:
                logging.warning('Failed to run pppd: %s', str(e))

            return False

        # non-blocking stdout
        util.set_blocking(self._pppd.stdout.fileno(), False)

        attempts = 200  # 20 secs
        while (self._pppd.poll() is None and \
                (not self.ifname or not self.ipaddr) and
                attempts):
            line = None
            try:
                line = self._pppd.stdout.readline().strip()
            except IOError, e:
                if e.errno == errno.EAGAIN:
                    time.sleep(0.1)
                    attempts -= 1
                    continue
                raise e

            if not line:
                continue

            logging.debug('PPPD: %s', line)

            if not self.ifname:
                matches = re.findall(r'Using\s+interface\s+([a-z0-9]+)', line)
                if matches:
                    self.ifname = matches[0]
            elif not self.ipaddr:
                matches = re.findall(r'local\s+IP\s+address\s+([0-9.]+)', line)
                if matches:
                    self.ipaddr = matches[0]
            #print 'attempt:', 200 - attempts,'line:',line

        if not self.ifname or not self.ipaddr:
            return False

        return True

    def _connect(self):
        """Register the device with a network provider."""

        logging.debug('Connecting modem...')

        self._modem.Register()

        opts = {
                'number':   MOBILE_GSM_NUMBER,
                'apn':      MOBILE_GSM_APN,
                'username': MOBILE_GSM_USER,
                'password': MOBILE_GSM_PASS
                }

        self._modem.Connect(opts)

        # Wait up to 3 secs until connected. (0.1s * 30 attempts = 3s)
        for _ in range(0, 30):
            if self._modem.State == mm.MM_MODEM_STATE_CONNECTED:
                return True

            time.sleep(0.1)
        return False

    def _disconnect(self):
        """Disconnect packet data connections."""

        logging.debug('Disconnecting modem...')

        if self._modem.State > mm.MM_MODEM_STATE_REGISTERED:  # registered/connected
            try:
                self._modem.Disconnect()
            except dbus.DBusException, e:
                logging.warning('Failed to disconnect the modem %s', str(e))
                return False

            # Wait up to 3 secs until disconnected. (0.1s * 30 attempts = 3s)
            for _ in range(0, 30):
                if self._modem.State < mm.MM_MODEM_STATE_DISCONNECTING:
                    return True

                time.sleep(0.1)
        return True
 
    def route_up(self):
        if self.is_ready():
            logging.debug('Activating %s default route', self.ifname)
            subproc.call(['ip', 'route', 'add', 'default', 'dev', self.ifname])

    def up(self):
        assert not self.remote

        if self.is_ready():
            return True

        self._enable(False)
        if not self._enable(True):
            return False

        if not self._connect():
            self._enable(False)
            return False

        if not self._pppd_connect():
            return False

        if not super(LinkMobile, self).up():
            return False
 
        self.route_up()

        return True

    def down(self):
        assert not self.remote

        if not self.state:
            return True

        success = super(LinkMobile, self).down()

        if self._pppd:
            util.set_blocking(self._pppd.stdout.fileno(), True)
            util.set_blocking(self._pppd.stderr.fileno(), True)
            self._pppd.terminate()
            self._pppd = None

        def async():
            try:
                self._modem.Disconnect()
                self._modem.Enable(False)
            except dbus.DBusException:
                pass

        Thread(target=lambda: async()).start()

        try:
            subproc.call(['killall', 'pppd'])
        except OSError:
            pass

        self.ifname = None

        return success

    def is_going_down(self):
        return super(LinkMobile, self).is_going_down()

