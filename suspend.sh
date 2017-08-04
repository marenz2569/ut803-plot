#!/bin/bash
# improved script from http://erste.de/UT61/index.html
for dat in /sys/bus/usb/devices/*;
	do
	if test -e $dat/manufacturer; then
		grep "1a86" $dat/idVendor > /dev/null && grep "e008" $dat/idProduct > /dev/null && echo auto > ${dat}/power/level && echo 0 > ${dat}/power/autosuspend
		exit
	fi
done
