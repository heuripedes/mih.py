mih.py
===
A IEEE 802.21-based media independent handover services implementation.

***USE THIS PROGRAM FOR EDUCATIONAL PURPOSES ONLY. IT WAS NOT MEANT FOR OR 
TESTED THOROUGHLY FOR REAL WORLD OR PRODUCTION USAGE. THIS SOFTWARE COMES
WITH NO WARRANTY AT ALL, USE AT YOUR OWN RISK. YOU HAVE BEEN WARNED!***

Differences from IEEE 802.21
===
No compatibility at all. This software was inspired by the standard and even 
has some of it's features, but it was meant to be used in a specific 
situation on the college I attend.

Assumptions
===
- Hardware doesn't change. In case of hardware change (e.g. an NIC 
  disapears), the behavior is undefined.

- The best link is always the one of the most reliable technology 
  (e.g. wifi > 3g).  If technology is the same, the best link is 
  either the one with best signal strenght or the first.

- The 3g Base Station do not support MIH-like services, at least not 
  the one implemented by this application. That means that no peer 
  discovery is done when you connect to a 3g network.

- There's no other application managing NICs. The program tries his 
  best to keep NIC information updated, but if an external program 
  changes anything the behavior is undefined.

Dependencies
===
Python 2.7
dbus
python-dbus
dbus-glib
ModemManager 0.6 (http://download.gnome.org/sources/ModemManager/0.6/ModemManager-0.6.0.0.tar.xz)

**Arch Linux:**
	pacman -S python2-dbus dbus-glib modemmanager


