#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-10-18
@author: shell.xu
'''
import sys, unittest

sys.path.append("../uniproxy")
import dnsserver

class LRUTest(unittest.TestCase):
    def setUp(self):
        self.lru = dnsserver.ObjHeap(10)

    def test_lru(self):
        for i in xrange(10): self.lru[i] = i
        for i in xrange(5): self.lru[i]
        for i in xrange(20, 25): self.lru[i] = i
        self.assertTrue(any(map(self.lru.get, xrange(5))))
        self.assertTrue(len(self.lru) <= 10)
