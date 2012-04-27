#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-04-25
@author: shell.xu
'''
import logging
from os import path

def import_config(*cfgs):
    d = {}
    for cfg in cfgs:
        try:
            with open(path.expanduser(cfg)) as fi:
                eval(compile(fi.read(), cfg, 'exec'), d)
        except OSError: pass
    return dict([(k, v) for k, v in d.iteritems() if not k.startswith('_')])

def initlog(lv):
    rootlog = logging.getLogger()
    handler = logging.StreamHandler()
    rootlog.addHandler(
        handler.setFormatter(
            logging.Formatter(
                '%(asctime)s,%(msecs)03d %(name)s[%(levelname)s]: %(message)s',
                '%H:%M:%S')) or handler)
    rootlog.setLevel(lv)
