# vim: sts=4 ts=8 sw=4 et

import os
from collections import namedtuple
from ctypes import *

# Load the C standard library
LibC = cdll.LoadLibrary("libc.so.6")

# netlink(7) constant for rtnetlink access
NETLINK_ROUTE = 0

# rtnetlink(7) constants

RTM_BASE	= 16

RTM_NEWLINK	= 16
RTM_DELLINK     = 17
RTM_GETLINK     = 18
RTM_SETLINK     = 19
RTM_NEWADDR	= 20
RTM_DELADDR     = 21
RTM_GETADDR     = 22

RTM_NEWROUTE	= 24
RTM_DELROUTE    = 25
RTM_GETROUTE    = 26

RTM_NEWNEIGH	= 28
RTM_DELNEIGH    = 29
RTM_GETNEIGH    = 30

RTM_NEWRULE	= 32
RTM_DELRULE     = 33
RTM_GETRULE     = 34

RTM_NEWQDISC	= 36
RTM_DELQDISC    = 37
RTM_GETQDISC    = 38

RTM_NEWTCLASS	= 40
RTM_DELTCLASS   = 41
RTM_GETTCLASS   = 42

RTM_NEWTFILTER	= 44
RTM_DELTFILTER  = 45
RTM_GETTFILTER  = 46

RTM_NEWACTION	= 48
RTM_DELACTION   = 49
RTM_GETACTION   = 50

RTM_NEWPREFIX	= 52

RTM_GETMULTICAST = 58

RTM_GETANYCAST	= 62

RTM_NEWNEIGHTBL	= 64
RTM_GETNEIGHTBL	= 66
RTM_SETNEIGHTBL = 67

RTM_NEWNDUSEROPT = 68

RTM_NEWADDRLABEL = 72
RTM_DELADDRLABEL = 73
RTM_GETADDRLABEL = 74

RTM_GETDCB = 78
RTM_SETDCB = 79

RawRtAttr = namedtuple('RawRtAttr', 'rta_len, rta_type, rta_data')
RawIfInfo = namedtuple('RawIfInfo', 'ifi_family, ifi_type, ifi_index, ifi_flags, ifi_change')

RawIfAddr = namedtuple('RawIfAddr', [
    'ifa_family',
    'ifa_prefixlen',
    'ifa_flags',
    'ifa_scope',
    'ifa_index'
])

RawRtMsg  = namedtuple('RawRtMsg', [
    'rtm_family',
    'rtm_dst_len',
    'rtm_src_len',
    'rtm_tos',
    'rtm_table',
    'rtm_protocol',
    'rtm_scope',
    'rtm_type',
    'rtm_flags'
])

def get_iface_list():
    """Returns a list of the local non-loopback interfaces"""

    ifaces = []

    with open('/proc/net/dev') as f:
        for line in f:
            if line.count('|') < 1:
                ifaces.append(line.strip().split(':')[0])

    ifaces.remove('lo') # discard loopback
    return ifaces

def get_ifinfo(name):
    """Returns a namedtuple containing the interface information."""
    import socket
    sock = socket.socket(socket.AF_NETLINK, socket.SOCK_RAW, NETLINK_ROUTE)
    sock.connect((os.getpid(), 0))




    return sock



class Link:
    def __init__(self, iface_name):
        """Constructor"""
        self._iface_name = iface_name
        self._iface


