# vim: ts=8 sts=4 sw=4 et nu

import os
import collections
import errno
import subprocess as subproc
import re
import time
import dbus
import logging

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
WIFI_THRESHOLD = 37
WIFI_SAMPLES = 10

# Mobile
MOBILE_GSM_NUMBER = '*99#'
MOBILE_GSM_APN = 'gprs.oi.com.br'
MOBILE_GSM_USER = 'oi'
MOBILE_GSM_PASS = 'oi'


def get_local_ifnames():
    """
    Looks for links in /proc/net/dev
    """

    # Local common interfaces pci/amr/virtual/etc
    prefixes = ('lo', 'virbr', 'vboxnet', 'ppp0', 'mon.')
    ifnames = [name for name in sockios.get_iflist() if not name.startswith(prefixes)]
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

    output = subproc.check_output(['iwconfig', ifname],
        stderr=open('/dev/null'))

    if re.findall('IEEE 802.11', output):
        return Link80211(**kwargs)

    return Link80203(**kwargs)


class Link(object):
    """Base class for links."""

    def __init__(self, **kwargs):

        self.ifname = None
        self.ipaddr = ''
        self.state = None  # force link_up on first poll()
        self.remote = False
        self.ready = False
        self.discoverable = True
        self.technology = 'unknown'

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
                (self.__class__.__name__, self.ifname, self.__dict__.get('ipaddr'))

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
            self.ipaddr = ifconf['in_addr']
        except sockios.error:
            self.ipaddr = ''

    def poll(self):
        """Refreshes the link object's state."""
        assert not self.remote

        self.state = sockios.is_up(self.ifname)

        if self.state:
            self._poll_ifconf()
        else:
            self.ipaddr = ''

    def poll_and_notify(self):
        """Refreshes the internal state and notifies users of link events."""
        assert not self.remote

        before = self.is_ready()

        self.poll()

        is_ready = self.is_ready()

        if before != is_ready:
            self.on_link_event(self, 'up' if is_ready else 'down')

    def up(self):
        """Set's the link's interface up."""
        assert not self.remote

        if not self.state:
            sockios.set_up(self.ifname)

            self.poll()

        return self.state

    def down(self):
        """Set's the link's interface down."""
        assert not self.remote

        if self.state:
            if self.is_ready():
                util.dhcp_release(self.ifname)

                subproc.call(['ip', 'addr', 'flush', 'dev', self.ifname])

                sockios.set_down(self.ifname)

                self.poll()

                if not self.state:
                    self.on_link_event(self, 'down')
            else:
                sockios.set_down(self.ifname)
                self.poll()

        return not self.state

    def is_ready(self):
        """Checks whether the link is ready."""
        return (getattr(self, '_ready', False) or
                (self.state and len(self.ipaddr)))

    def as_dict(self):
        """Returns the link's internal state as a dict()."""
        d = self.__dict__.copy()

        if self.remote and hasattr(d, '_ready'):
            d['ready'] = d['_ready']
            del d['_ready']

        del d['on_link_event']

        return d


class Link80203(Link):

    def __init__(self, **kwargs):
        self.technology = 'wired'
        self.strenght = 0

        super(Link80203, self).__init__(**kwargs)

    def update(self, *args, **kwargs):
        super(Link80203, self).update(*args, **kwargs)

    def poll(self):
        super(Link80203, self).poll()

        if self.state and self.ipaddr:
            self.strenght = WIRED_UP_STRENGHT
        else:
            self.strenght = WIRED_DOWN_STRENGHT

    def up(self):
        super(Link80203, self).up()

        if self.is_ready():
            return True

        if not super(Link80203, self).up():
            return False

        util.dhcp_release(self.ifname)
        util.dhcp_renew(self.ifname)

        self.poll()

        if self.is_ready():
            self.on_link_event(self, 'up')

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

        if not self.is_ready():
            return

        if self.is_going_down():
            self.on_link_event(self, 'going down')

    def up(self):
        assert not self.remote

        if self.is_ready():
            return True

        subproc.call(['rfkill', 'unblock', 'all'])

        if not super(Link80211, self).up():
            return False

        essid = WIFI_ESSID
        key = WIFI_KEY

        cmd = ['iwconfig', self.ifname, 'essid', essid]

        if key:
            cmd.append('key')
            cmd.append(key)

        if subproc.call(cmd) != 0:
            return False

        util.dhcp_release(self.ifname)
        util.dhcp_renew(self.ifname)

        self.poll()

        if self.is_ready():
            self.on_link_event(self, 'up')

        return self.is_ready()

    def is_going_down(self):
        return (len(self.samples) == WIFI_SAMPLES and
                util.average(self.samples) < WIFI_THRESHOLD)


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

        super(LinkMobile, self).__init__(**kwargs)

    def update(self, *args, **kwargs):
        super(LinkMobile, self).update(*args, **kwargs)

        self.ipaddr = None
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

        status = self._modem.GetStatus()

        self.state = (self._modem.State == mm.MM_MODEM_STATE_CONNECTED)

        if not self.state:
            return

        if not self.is_ready():
            self.strenght = 0
            self.samples.clear()
        else:
            self.strenght = status['signal-quality']
            self.samples.append(self.strenght)

        super(LinkMobile, self).poll()

    def poll_and_notify(self):
        super(LinkMobile, self).poll_and_notify()

    def _enable(self, enable):
        if enable:
            logging.debug('Enabling modem...')
        else:
            logging.debug('Disabling modem...')

        try:
            self._modem.Enable(enable)
            return True
        except dbus.DBusException, e:
            if enable:
                logging.debug('Failed to enable the modem: %s', str(e))
            else:
                logging.debug('Failed to disable the modem: %s', str(e))

            return False

    def _pppd_connect(self):  # osi data link layer (ppp)
        args = [
                '/usr/sbin/pppd',  # command
                'nodetach', 'lock', 'nodefaultroute', 'noipdefault',
                'noauth', 'crtscts', 'modem', 'usepeerdns',
                #'debug',
                '115200'  # baud
                ]

        if MOBILE_GSM_USER:
            args += ['user', MOBILE_GSM_USER]

        args += [self.m_device]

        #print 'Running pppd...'

        try:
            # XXX: pppd output must be unbufered or read()/write() will block.
            # in case pppd stdout is buffered, use UNIX sockets using
            # socket.socketpair()
            self._pppd = subproc.Popen(args, cwd='/', env={},
                    stdout=subproc.PIPE, stderr=subproc.PIPE)
        except IOError, e:
            logging.debug('Failed to run pppd: %s', str(e))
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

        opts = {
                'number':   MOBILE_GSM_NUMBER,
                'apn':      MOBILE_GSM_APN,
                'username': MOBILE_GSM_USER,
                'password': MOBILE_GSM_PASS
                }

        self._modem.Connect(opts, timeout=120)

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

        return True

    def down(self):
        assert not self.remote

        if not self.state or not self._pppd:
            return True

        success = super(LinkMobile, self).down()

        util.set_blocking(self._pppd.stdout.fileno(), True)
        util.set_blocking(self._pppd.stderr.fileno(), True)
        self._pppd.terminate()
        self._pppd = None

        self._modem.Disconnect()
        self._modem.Enable(False)

        self.ifname = None
        self.ipaddr = None

        return success

    def is_going_down(self):
        return super(LinkMobile, self).is_going_down()
