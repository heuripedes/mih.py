#!/usr/bin/env python2.7
# vim: ts=8 sts=4 sw=4 et ai nu

import mihf
import os

def _client_user(link, status, links):
    #print link, uplinks

    #print status, link, link.ifname, link.is_ready()
    #import traceback
    #traceback.print_stack()

    #print link.ifname, status

    if status == 'down' or status == 'going_down':

        current = mihf.current_link()

        if current and current.is_ready():
            return

        uplinks = [lnk for lnk in links if lnk.is_ready()]

        if link.remote or not uplinks:
            return
        
        
        better = uplinks[0]

        for l in uplinks:
            # wired is better than everything because i said so.
            if not l.wifi and not l.mobile:
                better = l
                break

            if l.strenght > better.strenght:
                better = l

        print "- Best link:", better.ifname

        if mihf.switch(better):
            print '- Switched to', better.ifname

    elif status == 'up':
        current = mihf.current_link() 
        
        # wired > wifi > mobile > None
        if (current != link and
            (not current or
            (current.mobile and not link.mobile) or
            (current.wifi and not link.wifi))):
            
            if mihf.switch(link):
                print '- Switched to', link.ifname

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

