#!/usr/bin/env python2.7
# vim: ts=8 sts=4 sw=4 et ai nu

import mihf
import os

WIFI_ESSID = 'GREDES_TELEMATICA'
WIFI_KEY   = ''

def _handle_link_changes(link, status, uplinks):
    print link, uplinks

    if status == 'down' and status == 'going_down':
        if link.remote or not uplinks:
            return

        better = uplinks[0]

        for l in uplinks:
            # wired is better than everything because i said so.
            if not l.wireless:
                better = l
                return

            if l.strenght > better.strenght:
                better = l

        mihf.switch(better)

    if status == 'up':
        if not link.wireless:
            mihf.switch(link)
        else:
            print "dunno wat to do"

if __name__ == '__main__':
    import sys
    import argparse

    argv = sys.argv[1:]

    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--server',
            action='store_true', help='Run as MIH server')

    args = parser.parse_args(argv)

    if args.server:
        mihf.serve()
    else:
        mihf.run(_handle_link_changes)


    sys.exit(0)

