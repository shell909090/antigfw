#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-05-03
@author: shell.xu
'''
from distutils.core import setup

version = '2.0'
description = 'toolset for cross GFW'
long_description = ' toolset for cross GFW, include such tools.\
  * auto start multi ssh tunnel\
  * http proxy use socks as upstream\
  * dns proxy use tcp over ssh'

setup(
    name='antigfw', version=version,
    description=description, long_description=long_description,
    author='Shell.E.Xu', author_email='shell909090@gmail.com',
    scripts=['dns2tcp.py', 'antigfw'],
    packages=['uniproxy',],
    data_files=[
        ('/etc/antigfw', ['data/antigfw.conf',]),
        ('share/uniproxy', ['data/dnsfake', 'data/reserved.list', 'data/routes.list.gz']),
        ])
