# vim: ts=8 sts=4 sw=4 et nu

import os
import socket
import subprocess
import errno
import shlex
import re
import logging
import time

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

    if count > 0:
        return total / count
    else:
        return 0

def unpickle(pickled):
    """Deserializes `pickled`."""
    return cPickle.loads(pickled)


def pickle(obj):
    """Serializes and optimizes `obj`."""
    return pickletools.optimize(cPickle.dumps(obj))

def call_timeout(args, **kwargs):
    """Implementation of subprocess.call that accepts a timeout.

    The default timeout is 20 seconds.

    Returns None if the process times out or the subprocess
    exit code"""

    timeout = kwargs.pop('timeout', 20)
    assert timeout > 0

    endtime = time.time() + timeout

    proc = subprocess.Popen(args, **kwargs)
    
    try:
        while time.time() < endtime:
            if proc.poll() != None:
                return proc.returncode
            time.sleep(1 * 0.05)
    except:
        raise

    try:
        proc.kill()
        print 'Killed "%s" (timeout).' % args[0]
    except:
        pass

    return None

def get_defroute_opts(ifname):

    args = ['ip', 'route', 'show', 'dev', ifname]
    matches = match_output('^default.*', args)

    if matches and matches[0].strip():
        return shlex.split(matches[0].strip())
 
    return ''

def dhcp_release(ifname):
    """Obtain a DHCP lease for `ifname`."""

    logging.debug('Releasing %s...', ifname)

    try:
        subprocess.call(['dhcpcd', '--release', ifname])
    except OSError, err:
        if err.errno != errno.ENOENT:
            raise err

        try:
            call_timeout(['dhclient', '-1', '-r', ifname], timeout=5)
        except OSError, err:
            if err.errno == errno.ENOENT:
                logging.critical('Neither dhcpcd nor dhclient were found.')
            else:
                raise err


def dhcp_renew(ifname):
    """Renews `ifname`'s DHCP lease."""

    logging.debug('Renewing %s DHCP lease...', ifname)

    try:
        subprocess.call(['dhcpcd', '--rebind', ifname])
    except OSError, err:
        if err.errno != errno.ENOENT:
            raise err

        try:
            call_timeout(['dhclient', '-1', ifname], timeout=5)
        except OSError, err:
            if err.errno == errno.ENOENT:
                logging.critical('Neither dhcpcd nor dhclient were found.')
            else:
                raise err


def bind_sock_to_device(sock, dev=''):
    """Binds `sock` to `dev`."""
    # TODO: use IP_PKTINFO
    # TODO: move to sockios
    sock.setsockopt(socket.SOL_SOCKET, SO_BINDTODEVICE, dev)


def match_output(pattern, cmd):
    """Matches `pattern` against the output of the call to `cmd`."""
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)

    return re.findall(pattern, subprocess.check_output(cmd))


def set_blocking(fildes, blocking):
    """Enables or disables the blocking I/O on `fildes`."""
    import fcntl

    flags = fcntl.fcntl(fildes, fcntl.F_GETFL)
    flags = flags | (os.O_NONBLOCK * (blocking == False))
    fcntl.fcntl(fildes, fcntl.F_SETFL, flags)


def link_value(link):
    """Calculates a value for the link using the given formula:

        v(l) = (w(l) + s(l)) * 2   if up(l) is true;
                w(l) + s(l)        otherwise.

        v(l) = link value
        w(l) = link weight (technology value/index)
        s(l) = link signal strength"""

    weight = {
            'mobile': 1,
            'wifi':   2,
            'wired':  3
            }

    value = weight[link.technology] * 10000 + link.strenght
    value += value * link.is_ready()  # double if link is up

    return value


def link_compare(a, b):
    """Compares two links. Returns -1, 0 or 1 depending on whether the *a*
    link is considered worse, similar or better than *b*."""

    # wired > anything
    if not a.is_wifi() and not a.is_mobile() and (b.is_wifi() or b.is_mobile()):
        return 1

    # wifi > mobile unless wifi is going down.
    if a.is_wifi() and b.is_mobile():
        return a.is_going_down() == False

    # if its the same tech, signal strength decides who's better
    if type(a) == type(b):
        delta = a.strenght - b.strenght
        return delta / abs(delta) if delta != 0 else 0

    return 0

