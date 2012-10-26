#!/usr/bin/env python2.7
# vim: ts=8 sts=4 sw=4 et nu

import mihf
import mihf.util as util
import logging

def client_remote_link_handler(mihf, link, status, scope):
    pass

def client_local_link_handler(mihf, link, state, scope):
    current = mihf.current_link

    logging.info('Link %s is %s', link, state)
    
    # Try to switch if the current link is down or going down.
    if current == link and (state == 'down' or state == 'going down'):
        up_links = [l for l in mihf.links if l.is_ready()]

        if not up_links:
            logging.warning('No suitable link to fallback.')
            return
        
        better = sorted(up_links, util.link_compare)[0]

        if mihf.switch(better):
            logging.info('Switched to %s.', better.ifname)

    # Try to use the newly available link as main if we're not connected at 
    # the moment. Send discovery message if the switching succeed.
    if not current and state == 'up':
        if mihf.switch(link):
            logging.info('Switched to %s.', link.ifname)
            mihf.discover(link)
        else:
            logging.info('Failed to switch to to %s.', link.ifname)
        

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
        f = mihf.ClientMihf({
            'local': client_local_link_handler,
            'remote': client_remote_link_handler
            })

    f.run()


    sys.exit(0)

if __name__ == '__main__':
    main()
    

    

