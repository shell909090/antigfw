#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-10-14
@author: shell.xu
'''
import copy, zlib, json, base64, random, cStringIO
from http import *
from gae import *

def get_request(d):
    d = d.replace('&', '').replace('=', '')
    d = msg_decoder(d, 'XOR', '1234567890123456')
    print d
    reqx, options = loadreq(d)
    print reqx, options

