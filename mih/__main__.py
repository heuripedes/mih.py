#!/usr/bin/env python2.7
# vim: ts=8 sts=4 sw=4 et nu

from mih.mihf import mihf
from mih.mihf import util
import logging


def find_alt_link(current, llinks, rlinks):
    for rlink in rlinks:
        # discard same-technology links
        if rlink.technology == current.technology:
            continue

        # discard down remote links
        if not rlink.is_ready():
            continue

        for llink in llinks:
            # discard this link
            if current == llink:
                continue

            if llink.technology == rlink.technology:
                yield llink


class MihServer:
    pass


class MihClient:
    @staticmethod
    def link_up(mihf, link):
        if link.remote:
            return

        if not mihf.current_link:
            if mihf.switch(link):
                logging.info('Switched to %s.', link.ifname)
            else:
                logging.info('Failed to switch to to %s.', link.ifname)

        mihf.discover(link)

    @staticmethod
    def link_down(mihf, link):
        if link.remote:
            return

        links = mihf.links.values()
        current = mihf.current_link
        up_links = [l for l in links if l.is_ready()]

        # nothing else to do.
        if current != link:
            return

        # find an alternative tech link related to server's link report
        if mihf.last_report:
            alinks = find_alt_link(current, links, mihf.last_report)
            for alink in sorted(alinks, util.link_compare):
                if mihf.switch(alink):
                    logging.info('Switched to %s.', alink.ifname)
                    mihf.discover(alink)
                    break

            mihf.last_report = None

        # switch to an up link if we can
        elif up_links:
            better = sorted(up_links, util.link_compare)[0]

            if mihf.switch(better):
                logging.info('Switched to %s.', better.ifname)
                mihf.discover(better)

        else:
            logging.debug('Attempting to bring one link up...')
            # try to set one link up when there's none available
            for lnk in links:
                if lnk != link and mihf.switch(lnk):
                    logging.info('Switched to %s.', lnk.ifname)
                    mihf.discover(lnk)
                    break

    @staticmethod
    def link_going_down(mihf, link):
        if link.remote:
            return

        links = mihf.links.values()
        current = mihf.current_link

        if current != link:
            return

        if mihf.last_report:
            alinks = find_alt_link(current, links, mihf.last_report)
            for alink in sorted(alinks, util.link_compare):
                if mihf.switch(alink):
                    logging.info('Switched to %s.', alink.ifname)
                    mihf.discover(link)
                    break

            mihf.last_report = None
        else:
            mihf.report()


def main():
    import sys
    import argparse
    import os

    os.chdir('/')

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
        f = mihf.ServerMihf(MihServer)
    else:
        f = mihf.ClientMihf(MihClient)

    f.run()

    sys.exit(0)

if __name__ == '__main__':
    main()
