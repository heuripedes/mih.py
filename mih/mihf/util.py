# vim: ts=8 sts=4 sw=4 et nu

import os
import socket
import resource
import subprocess
import errno
import shlex
import re

import cPickle
import pickletools

# from sys/socket.h
SO_BINDTODEVICE = 25

def gen_id(prefix=''):
    """
    :return prefix+random hex number
    """

    return (prefix + str(os.urandom(4)).encode('hex_codec')).upper()


def average(samples):
    """Calculates the average of the non-zero entries in `samples`."""
    count = len(samples)
    total = 0
    for sample in samples:
        if sample == 0:
            count = count - 1
        else:
            total = total + sample

    return total / count


def unpickle(pickled):
    """Deserializes `pickled`."""
    return cPickle.loads(pickled)


def pickle(obj):
    """Serializes and optimizes `obj`."""
    return pickletools.optimize(cPickle.dumps(obj))


def dhcp_release(ifname):
    """Obtain a DHCP lease for `ifname`."""
    retcode = False
    try:
        subprocess.call(['dhcpcd', '--release', ifname])
    except OSError, e:
        if not e.errno == errno.ENOENT:
            raise e

        try:
            subprocess.call(['dhclient', '-r', ifname])
        except OSError, e:
            if not e.errno == errno.ENOENT:
                raise e

            print '- DHCP client program not found. Please install dhcpcd or dhclient.'

def dhcp_renew(ifname):
    """Renews `ifname`'s DHCP lease."""
    retcode = False

    try:
        retcode = subprocess.call(['dhcpcd', '--rebind', ifname])
    except OSError, e:
        if not e.errno == errno.ENOENT:
            raise e

        try:
            retcode = subprocess.call(['dhclient', ifname])
        except OSError, e:
            if not e.errno == errno.ENOENT:
                raise e

            print '- DHCP client program not found. Please install dhcpcd or dhclient.'
            retcode = 1

    return retcode == 0

def bind_sock_to_device(sock, dev = ''):
    """Binds `sock` to `dev`."""
    # TODO: use IP_PKTINFO
    # TODO: move to sockios
    sock.setsockopt(socket.SOL_SOCKET, SO_BINDTODEVICE, dev)

def match_output(pattern, cmd):
    """Matches `pattern` against the output of the call to `cmd`."""
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)

    return re.findall(pattern, subprocess.check_output(cmd))

def set_blocking(fd, blocking):
    """Enables/disables the blocking I/O on `fd`."""
    import fcntl

    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    flags = os.O_NONBLOCK * (blocking == False)
    fcntl.fcntl(fd, fcntl.F_SETFL, flags)

def link_value(link):
    """Calculates a value for the link using the given formula:
          
        v(l) = (w(l) + s(l)) * 2   if up(l) is true;
                w(l) + s(l)        otherwise.
        
        v(l) = link value
        w(l) = link weight (technology value/index)
        s(l) = link signal strenght"""
    
    weight = {
            'mobile': 1,
            'wifi':   2,
            'wired':  3
            }

    value = weight[link.technology] * 10000 + link.strenght
    value += value * link.is_ready() # double if link is up

    return value

def link_compare(a, b):
    """Compares two links. Returns -1, 0 or 1 depending on whether the *a* 
    link is considered worse, similar or better than *b*."""
    
    # wired > anything
    if not a.is_wifi() and not a.is_mobile() and (b.is_wifi() or b.is_mobile()):
        return 1

    # wifi > mobile
    if a.is_wifi() and b.is_mobile():
        return 1

    # if its the same tech, signal strenght decides who's better
    if type(a) == type(b):
        delta = a.strenght - b.strenght
        return delta/abs(delta) if delta != 0 else 0

    return 0

