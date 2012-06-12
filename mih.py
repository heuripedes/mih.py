#!/usr/bin/env python2.7
# vim: ts=8 sts=4 sw=4 et ai nu

import mihf

def _handle_link_changes(link, status):
    if status == 'up':
        pass
    if status == 'down':
        pass
    if status == 'going_down':
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

