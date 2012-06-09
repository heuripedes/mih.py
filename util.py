# vim: ts=8 sts=4 sw=4 et ai nu

import socket
import resource

def normalize(s):
    return s.ljust(resource.getpagesize(), '\x00')

def recvfrom(sock):
    data = None
    try:
        data = sock.recvfrom(resource.getpagesize())
    except socket.timeout:
        pass

    return data

def sendto(sock, addr, data):
    try:
        return sock.sendto(normalize(data), 0, addr)
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
