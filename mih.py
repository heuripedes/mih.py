#!/usr/bin/env python2
# vim: sts=4 ts=8 sw=4 et

if __name__ == "__main__":
    import mihf

    f = mihf.Mihf()
    f.add_service(mihf.Mies())

    f.run()


