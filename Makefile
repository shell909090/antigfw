#!/usr/bin/make -f

PROJ_NAME=antigfw

all: build

build-deb: build
	dpkg-buildpackage -rfakeroot

build:

clean:
	rm -f *.pyc *.pyo
	rm -rf build
	rm -f python-build-stamp*
	rm -rf debian/$(PROJ_NAME)
	rm -rf debian/python-$(PROJ_NAME)
	rm -f debian/python-$(PROJ_NAME)*
	rm -f debian/pycompat
	rm -rf debian/python-module-stampdir

install:
