# vim: ts=8 sts=4 sw=4 et ai nu

import os
import socket
import resource

def gen_id(name):
    """
    :return name+random hex number
    """

    return (name.strip() + '-' + str(os.urandom(4)).encode('hex_codec')).upper()

def average(samples):
    return reduce(lambda total, value: total + value, samples) / len(samples)

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
