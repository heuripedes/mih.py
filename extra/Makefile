
ssid=GREDES_MIH
incoming=wlan0
outgoing=p6p1

path=$(shell realpath .)

hostapd_pid=$(path)/hostapd.pid
dnsmasq_pid=$(path)/dnsmasq.pid
dnsmasq_conf=$(path)/dnsmasq.conf
dnsmasq_log=$(path)/dnsmasq.log
hostapd_conf=$(path)/hostapd.conf

all:
	@echo targets: start stop clean

stop: stop_hostapd stop_dnsmasq stop_ip
start: start_hostapd start_dnsmasq
clean: stop

check_deps:
	@((which realpath &> /dev/null) || (echo 'missing program: realpath' && exit 1))
	@((which hostapd &> /dev/null)  || (echo 'missing program: hostapd' && exit 1))
	@((which dnsmasq &> /dev/null)  || (echo 'missing program: dnsmasq' && exit 1))
	@((which iptables &> /dev/null) || (echo 'missing program: iptables' && exit 1))
	@((which ip &> /dev/null)  || (echo 'missing program: ip (iproute2)' && exit 1))

start_ip: stop_ip
	-rfkill unblock all
	sysctl net.ipv4.ip_forward=1
	ip addr add 192.168.0.1 dev $(incoming)
	iptables -t nat -A POSTROUTING -s 192.168.0.0/24 -o $(outgoing) -j MASQUERADE

stop_ip:
	-iptables -F
	-iptables -t nat -F
	-iptables -P FORWARD ACCEPT
	-iptables -P OUTPUT ACCEPT
	-iptables -P INPUT ACCEPT
	-ip addr flush dev $(incoming)

start_dnsmasq: stop_dnsmasq start_ip
	echo > $(dnsmasq_conf)
	dnsmasq --interface=$(incoming)\
		--dhcp-range=192.168.0.50,192.168.0.150,12h\
		--pid-file=$(dnsmasq_pid)\
		--conf-file=$(dnsmasq_conf)\
		--log-facility=$(dnsmasq_log)

stop_dnsmasq:
	-service dnsmasq stop
	-systemctl stop dnsmasq.service
	-kill `cat $(dnsmasq_pid)`
	-killall dnsmasq
	-killall -9 dnsmasq
	-rm -f $(dnsmasq_conf) $(dnsmasq_pid) $(dnsmasq_log)

start_hostapd: stop_hostapd start_ip
	echo -e 'interface=$(incoming)\nssid=$(ssid)' > $(hostapd_conf)
	echo -e 'driver=nl80211\nhw_mode=g\nchannel=6' >> $(hostapd_conf)
	hostapd -B -P $(hostapd_pid) $(hostapd_conf)
	
stop_hostapd:
	-service hostapd stop
	-systemctl stop hostapd.service
	-kill `cat $(hostapd_pid)`
	-killall hostapd
	-killall -9 hostapd
	-rm -f $(hostapd_pid) $(hostapd_conf)


