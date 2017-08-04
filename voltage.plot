system("cat /tmp/ut803 | grep voltage | grep -v overload | cut -f2 -d' ' > /tmp/voltage")
plot "/tmp/voltage"
replot
pause 1
reread
