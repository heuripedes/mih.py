#!/usr/bin/env python2.7
# vim: ts=8 sts=4 sw=4 et nu

import mihf
import logging

def client_user(mihf, link, status):
    current = mihf.current_link

    if status == 'down' or status == 'going down':
        
        if current and current.is_ready():
            return

        up_links = [l for l in mihf.links if l.is_ready()]

        if link.remote or not up_links:
            return

        better = up_links[0]

        for l in uplinks:
            # wired is better than everything because i said so.
            if not l.wifi and not l.mobile:
                better = l
                break

            # wifi is better than mobile 
            if l.wifi and better.mobile:
                better = l
            
            # if its the same tech, signal strenght decides who's better
            if (((l.wifi and better.wifi) or (l.mobile and better.mobile)) and 
                (l.strenght > better.strenght)):
                    better = l

        print '- Best link:', better.ifname

        if mihf.switch(better):
            print '- Switched to', better.ifname


    elif status == 'up':

        if current == link:
            return

        if (not current or
            (current.mobile and not link.mobile) or
            (current.wifi and not link.wifi)):

            if mihf.switch(link):
                print '- Switched to', link.ifname

        mihf.discover(link)


def main():
    import sys
    import argparse

    argv = sys.argv[1:]

    parser = argparse.ArgumentParser(prog=sys.argv[0])

    parser.add_argument('-s', '--server',
        action='store_true',
        help='run as server')

    parser.add_argument('-L', '--loglevel',
        action='store', default='DEBUG',
        help='set the logging level')

    args = parser.parse_args(argv)

    logging.basicConfig(
        format='(%(filename)s:%(lineno)d) %(levelname)s: %(message)s',
        level=getattr(logging, args.loglevel)
    )

    f = None

    if args.server:
        f = mihf.ServerMihf(lambda a, b, c: None)
    else:
        f = mihf.ClientMihf(client_user)

    f.run()


    sys.exit(0)

if __name__ == '__main__':
    main()
    

    

