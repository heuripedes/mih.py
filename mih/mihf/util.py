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
    count = len(samples)
    total = 0
    for sample in samples:
        if sample == 0:
            count = count - 1
        else:
            total = total + sample

    return total / count


def unpickle(pickled):
    return cPickle.loads(pickled)


def pickle(object):
    return pickletools.optimize(cPickle.dumps(object))


def normalize(s):
    return s.ljust(resource.getpagesize(), '\x00')


def recvfrom(sock):
    try:
        return sock.recvfrom(resource.getpagesize())
        #if data:
        #    print '<',data[1],len(data[0]),'bytes.'

    except socket.timeout:
        return None, None


def sendto(sock, addr, data):
    try:
        sent = sock.sendto(normalize(data), 0, addr)
        #print '>',addr,sent,'bytes.'

        return sent
    except socket.timeout:
        pass

    return 0


def accept(sock):
    csock = None
    try:
            csock, _ = sock.accept()
    except socket.timeout:
            pass
    except socket.error as e:
            raise e

    return csock

def iface_up(ifname):
    import platform

def dhcp_release(ifname):
    retcode = False
    try:
        subprocess.call(['dhcpcd', '--release', ifname])
    except OSError as e:
        if not e.errno == errno.ENOENT:
            raise e

        try:
            subprocess.call(['dhclient', '-r', ifname])
        except OSError as e:
            if not e.errno == errno.ENOENT:
                raise e

            print '- DHCP client program not found. Please install dhcpcd or dhclient.'

def dhcp_renew(ifname):
    retcode = False

    try:
        retcode = subprocess.call(['dhcpcd', '--rebind', ifname])
    except OSError as e:
        if not e.errno == errno.ENOENT:
            raise e

        try:
            retcode = subprocess.call(['dhclient', ifname])
        except OSError as e:
            if not e.errno == errno.ENOENT:
                raise e

            print '- DHCP client program not found. Please install dhcpcd or dhclient.'
            retcode = 1

    return retcode == 0

def bind_sock_to_device(sock, dev = ''):
    # TODO: use IP_PKTINFO
    sock.setsockopt(socket.SOL_SOCKET, SO_BINDTODEVICE, dev)

def match_output(pattern, cmd):
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)

    return re.findall(pattern, subprocess.check_output(cmd))

