# vim: ts=8 sts=4 sw=4 et nu

# ModemManager/DBus wrapper

import dbus
import logging

MM_DBUS_PATH = '/org/freedesktop/ModemManager'
MM_DBUS_SERVICE = 'org.freedesktop.ModemManager'

MM_DBUS_INTERFACE = 'org.freedesktop.ModemManager'
MM_DBUS_INTERFACE_MODEM = 'org.freedesktop.ModemManager.Modem'
MM_DBUS_INTERFACE_MODEM_CDMA = 'org.freedesktop.ModemManager.Modem.Cdma'
MM_DBUS_INTERFACE_MODEM_GSM_CARD = 'org.freedesktop.ModemManager.Modem.Gsm.Card'
MM_DBUS_INTERFACE_MODEM_GSM_NETWORK = 'org.freedesktop.ModemManager.Modem.Gsm.Network'
MM_DBUS_INTERFACE_MODEM_SIMPLE = 'org.freedesktop.ModemManager.Modem.Simple'

MM_MODEM_TYPE_UNKNOWN = 0
MM_MODEM_TYPE_GSM = 1
MM_MODEM_TYPE_CDMA = 2

MM_MODEM_STATE_UNKNOWN = 0
MM_MODEM_STATE_DISABLED = 10
MM_MODEM_STATE_DISABLING = 20
MM_MODEM_STATE_ENABLING = 30
MM_MODEM_STATE_ENABLED = 40
MM_MODEM_STATE_SEARCHING = 50
MM_MODEM_STATE_REGISTERED = 60
MM_MODEM_STATE_DISCONNECTING = 70
MM_MODEM_STATE_CONNECTING = 80
MM_MODEM_STATE_CONNECTED = 90


class ModemManagerWrapper(object):

    def __init__(self):
        self.bus = dbus.SystemBus()

        self.proxy = self.bus.get_object(MM_DBUS_SERVICE, MM_DBUS_PATH)
        self.iface = dbus.Interface(self.proxy, dbus_interface=MM_DBUS_INTERFACE)

    def EnumerateDevices(self):
        """Get the list of modem devices."""
        return self.iface.EnumerateDevices()


ModemManager = None
try:
    ModemManager = ModemManagerWrapper()
except dbus.DBusException, e:
    logging.critical('Failed to access ModemManager DBus service: %s', str(e))
    raise e


class Modem(object):

    def __init__(self, name):
        assert name

        self.name = name

        self._proxy = ModemManager.bus.get_object(MM_DBUS_INTERFACE, name)
        self._props = dbus.Interface(self._proxy, dbus_interface='org.freedesktop.DBus.Properties')
        self._modem = dbus.Interface(self._proxy, dbus_interface=MM_DBUS_INTERFACE_MODEM)
        self._simple = dbus.Interface(self._proxy, dbus_interface=MM_DBUS_INTERFACE_MODEM_SIMPLE)

    def __getattr__(self, name):
        return self._props.Get(MM_DBUS_INTERFACE_MODEM, name)

    def __getstate__(self):
        return {}

    @property
    def State(self):
        """Wrapper for org.freedesktop.ModemManager.Modem.State property."""

        try:
            return self._props.Get(MM_DBUS_INTERFACE_MODEM, 'State')
        except dbus.DBusException:
            status = self.GetStatus()
            return status['state']

    def GetStatus(self):
        """Get the modem status."""
        return self._simple.GetStatus()

    def Enable(self, enable):
        """Enable the device. Initializes the modem."""
        self._modem.Enable(enable)

    def Connect(self, options):
        """Dial in."""
        self._simple.Connect(options)

    def Register(self, network_id=''):
        """Register the device to the network"""
        if self.Type == MM_MODEM_TYPE_GSM:
            self._gsm.Register(network_id)

    def Disconnect(self):
        """Disconnect modem."""
        self._modem.Disconnect()

    def GetInfo(self):
        """Get the card information (manufacturer, modem, version). """
        return self._modem.GetInfo()

    def Reset(self):
        return self._modem.Reset()
