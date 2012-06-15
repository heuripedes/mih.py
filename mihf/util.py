# vim: ts=8 sts=4 sw=4 et ai nu

import os
import socket
import resource
import math
import subprocess
import errno

def gen_id(name):
    """
    :return name+random hex number
    """

    return (name.strip() + '-' + str(os.urandom(4)).encode('hex_codec')).upper()


def average(samples):
    return math.fsum(samples) / len(samples)


def normalize(s):
    return s.ljust(resource.getpagesize(), '\x00')


def recvfrom(sock):
    data = None
    try:
        data = sock.recvfrom(resource.getpagesize())
        #if data:
        #    print '<',data[1],len(data[0]),'bytes.'

    except socket.timeout:
        pass

    return data


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

def lease_renew(ifname):
    success = False
    try:
        success = subprocess.call(['dhcpcd', '--release', ifname])
        success = success and subprocess.call(['dhcpcd', '--rebind', ifname])
    except OSError as e:
        if not e.errno == errno.ENOENT:
            raise e

        try:
            success = subprocess.call(['dhclient', '-r', ifname])
            success = success and subprocess.call(['dhclient', ifname])
        except OSError as e:
            if not e.errno == errno.ENOENT:
                raise e

            print '- DHCP client program not found. Please install dhcpcd or dhclient.'
            success = False

    return success
