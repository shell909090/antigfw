### Makefile --- 

## Author: shell@DSK
## Version: $Id: Makefile,v 0.0 2012/10/28 15:52:13 shell Exp $
## Keywords: 
## X-URL: 
TARGET=dns2tcp dnsproxy

all: $(TARGET)

clean:
	rm -rf *.c *.pyx $(TARGET)

dns2tcp.c: dns2tcp.py
	cython --embed $^

dns2tcp: dns2tcp.c
	gcc $(shell python-config --includes) $(shell python-config --libs) -O2 -o $@ $^
	strip $@
	chmod 755 $@

dnsproxy.pyx: dnsproxy.py
	python sc.py $^ $@

dnsproxy.c: dnsproxy.pyx
	cython --embed $^

dnsproxy: dnsproxy.c
	gcc $(shell python-config --includes) $(shell python-config --libs) -O2 -o $@ $^
	strip $@
	chmod 755 $@

### Makefile ends here
