#!/bin/bash
while sleep 1;
do
	sudo ./suspend.sh && ./he2325u_hidapi.py | ./es51922.py -m plot -f /tmp/ut803;
done
