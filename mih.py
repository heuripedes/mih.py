#!/usr/bin/env python2.7
# vim: ts=8 sts=4 sw=4 et ai nu

import mihf
import os

def _client_user(link, status, links):
    #print link, uplinks

    uplinks = [link for link in links if link.ready()]
    print status, link, link.ifname, link.ready()
    import traceback
    traceback.print_stack()

    if status == 'down' or status == 'going_down':
        if link.remote or not uplinks:
            return
        print uplinks
        better = uplinks[0]

        for l in uplinks:
            # wired is better than everything because i said so.
            if not l.wireless:
                better = l
                return

            if l.strenght > better.strenght:
                better = l

        mihf.switch(better)
    elif status == 'up':
        current = mihf.current_link() 
        
        if not current:
            mihf.switch(link)
        else:
            if current.mobile and not link.mobile:
                mihf.switch(link)
        mihf.discover(link)


def _server_user(link, status, uplinks):

    if status == 'up' and not link.ipaddr:
        link.up()
        

if __name__ == '__main__':
    import sys
    import argparse

    argv = sys.argv[1:]

    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--server',
            action='store_true', help='Run as MIH server')

    args = parser.parse_args(argv)

    if args.server:
        mihf.serve(_server_user)
    else:
        mihf.run(_client_user)


    sys.exit(0)

