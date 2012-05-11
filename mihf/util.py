# vim: sts=4 ts=8 sw=4 et

import os

def gen_id(name):
    """
    Generates an identifier string.

    The string is formatted as "NR", where N is the provided name and R is a
    hex-encoded randomly generated 32bit number. N is strip()ed and the 
    entire string is converted to uppercase.
    """
    
    return (name.strip() + os.urandom(4).encode('hex')).upper()

