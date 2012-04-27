#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-04-17
@author: shell.xu
'''
import logging
logger = logging.getLogger('caller')

class CallMapping(object):

    def __init__(self):
        self.map = {}
        self.default = None

    def __call__(self, cmd, *ps, **kw):
        func = self.map.get(cmd, self.default)
        logger.debug('%s is called.' % func.__name__)
        return func(cmd, *ps, **kw)

    def set_default(self, func):
        self.default = func
        return func

    def register(self, *names):
        def reciver(func):
            for name in names: self.map[name] = func
            return func
        return reciver

class CallHook(object):

    def __init__(self, *hooks):
        self.hooks = hooks

    def __call__(self, *ps):
        return [hook(*ps) for hook in self.hooks]

    def register(self, func):
        self.hooks.append(func)

    def unregister(self, func):
        self.hooks.remove(func)
