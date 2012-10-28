### Makefile --- 

## Author: shell@DSK
## Version: $Id: Makefile,v 0.0 2012/10/28 15:52:13 shell Exp $
## Keywords: 
## X-URL: 

all: dns2tcp

dns2tcp.c: dns2tcp.py
	cython --embed $^

dns2tcp: dns2tcp.c
	gcc $(shell python-config --includes) $(shell python-config --libs) -O2 -o $@ $^

### Makefile ends here
