#!/usr/bin/env python2.7
# vim: ts=8 sts=4 sw=4 et nu

from mih.mihf import mihf
from mih.mihf import util
import logging


def find_alt_link(current, llinks, rlinks):
    """Find local links compatible to remote links."""
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


def switch_to_better(func, links):
    """Switches to the better link in links."""
    links = sorted(links, util.link_compare)

    for link in links:
        if func.switch(link):
            func.discover(link)
            return True
    return False


class MihServer:
    pass


class MihClient:
    """Comodity class to group client-specific behaviour.

    This class is composed by three main methods, which are triggers for the 
    link events emited by the MIHF: `link_up`, `link_down`, `link_going_down`. 
    All methods perform link switching but each employs a different heuristic. 
    It should be noted that they only perform link switching to/from local 
    links."""

    def __init__(self):
        pass

    @staticmethod
    def link_up(func, link):
        """Trigger for the link up event.

        This method will switch to the link which triggered the event when the 
        MIHF is not connected to any other link. If the link which triggered the
        event is considered to be better than the current link, `discovery` is 
        called on it."""

        logging.info('Link %s is up', link)

        if link.remote or not link.state:
            return

        if func.current_link:
            # switch to non-mobile network
            if func.current_link.is_mobile() and not link.is_mobile() and func.switch(link):
                func.discover(link)
        else:
            if func.switch(link):
                # XXX: is this needed? wont the up event perform this anyways?
                func.discover(link)
                pass
            else:
                logging.warning('Failed to switch to to %s.', link.ifname)

    @staticmethod
    def link_down(func, link):
        """Trigger for the link down event.

        This method will not perform any link switching unless the down link is 
        the currently connected one. In that case, the method will inspec the 
        results of the last `discovery` looking for an alternative technology 
        link. If there's no cached discovery result, the method will try to 
        switch to the best link that happens to be up. If there's no up link, 
        the method will attempt to bring any link up."""


        logging.info('Link %s is down', link)

        if link.remote or link.state:
            return

        links = func.links.values()
        current = func.current_link
        up_links = [l for l in links if l.state]

        # nothing else to do.
        if current != link:
            return

        # find an alternative tech link related to server's link report
        if func.last_report:
            logging.info('Inspecting server report...')

            alinks = find_alt_link(current, links, func.last_report)
            switch_to_better(func, alinks)

            func.last_report = None

        # switch to an up link if we can
        elif up_links:
            logging.info('Searching for alternative link...')
            switch_to_better(func, up_links)

        # desperately try to bring one link up
        else:
            logging.info('Attempting to bring one link up...')
            switch_to_better(func, links)

    @staticmethod
    def link_going_down(func, link):
        """Trigger for the link_going_down event

        This method will perform link switching only when 
        there's an cached `discovery` report. The method will instruct the MIHF 
        to switch to the available link with the best technology."""

        logging.info('Link %s is going down', link)

        if link.remote:
            return

        links = func.links.values()
        current = func.current_link

        if current != link:
            return

        if func.last_report:
            alinks = find_alt_link(current, links, func.last_report)

            switch_to_better(func, alinks)

            func.last_report = None
        else:
            func.report()


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
        action='store', default='INFO',
        help='set the logging level (WARNING|INFO|DEBUG)')

    args = parser.parse_args(argv)

    logging.basicConfig(
        format='(%(filename)s:%(lineno)d) %(levelname)s: %(message)s',
        level=getattr(logging, args.loglevel)
    )

    func = None

    if args.server:
        func = mihf.ServerMihf(MihServer)
    else:
        func = mihf.ClientMihf(MihClient)

    func.run()

    sys.exit(0)

if __name__ == '__main__':
    main()

