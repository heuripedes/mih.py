
ssid=GREDES_MIH
incoming=wlan0
outgoing=p6p1

path=$(shell realpath .)

hostapd_pid=$(path)/hostapd.pid
dnsmasq_pid=$(path)/dnsmasq.pid
dnsmasq_conf=$(path)/dnsmasq.conf
hostapd_conf=$(path)/hostapd.conf

all:
start:
	echo -e 'interface=$(incoming)\nssid=$(ssid)' > $(hostapd_conf)
	echo -e 'driver=nl80211\nhw_mode=g\nchannel=6' >> $(hostapd_conf)
	hostapd -B -P $(hostapd_pid) $(hostapd_conf)
	iptables -t nat -A POSTROUTING -s 192.168.0.0/24 -o $(outgoing) -j MASQUERADE
	dnsmasq --interface=$(incoming) --dhcp-range=192.168.0.50,192.168.0.150,12h --pid-file=$(dnsmasq_pid) --conf-file=$(dnsmasq_conf)

stop:
	-kill `cat $(hostapd_pid)`
	-kill `cat $(dnsmasq_pid)`
	iptables -t nat -F

clean: stop
	-rm -f $(hostapd_pid) $(hostapd_conf) $(dnsmasq_pid) $(dnsmasq_conf)


