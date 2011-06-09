#!/usr/bin/make -f

all: build

build:
	dpkg-buildpackage -rfakeroot

clean:
	debian/rules clean
