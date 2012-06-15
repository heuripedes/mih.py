#!/usr/bin/env python2.7
# vim: ts=8 sts=4 sw=4 et ai nu

import mihf
import os

WIFI_ESSID = 'GREDES_TELEMATICA'
WIFI_KEY   = ''

def _handle_link_changes(link, status):
    if status == 'up':
        print 'user:',link.ifname,'is up'

        if link.remote
            return

        if not link.wireless:
            if link.carrier and not link.ipaddr:
                link.up()

    if status == 'down':
        print 'user:',link.ifname,'is down'

        if link.remote
            return

        pass

    if status == 'going_down':
        print 'user:',link.ifname,'is going down'

        if link.remote
            return

        pass

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

