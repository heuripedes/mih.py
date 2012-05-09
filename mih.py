#!/usr/bin/env python2

if __name__ == "__main__":
	import miis
	import mies
	import mics
	import mihf

	f = mihf.Mihf()

	f.add_service(miis.Miis())
	f.add_service(mies.Mies())
	f.add_service(mics.Mics())

	f.run()


