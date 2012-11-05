#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-11-05
@author: shell.xu
'''
import urllib2, unittest

auth_handler = urllib2.HTTPBasicAuthHandler()
auth_handler.add_password(
    realm='managers', uri='http://127.0.0.1:8080/', user='admin', passwd='uniproxy')
auth_opener = urllib2.build_opener(auth_handler)

class ManagerAuth(unittest.TestCase):
    def test_noauth(self):
        with self.assertRaises(urllib2.HTTPError):
            urllib2.urlopen('http://127.0.0.1:8080/')
    def test_auth(self):
        auth_opener.open('http://127.0.0.1:8080/')

class ManagerTest(unittest.TestCase):
    def test_stat(self):
        auth_opener.open('http://127.0.0.1:8080/')
    def test_dnsfake(self):
        auth_opener.open('http://127.0.0.1:8080/dnsfake')
    def test_whitenets(self):
        auth_opener.open('http://127.0.0.1:8080/whitenets')
    def test_blacknets(self):
        auth_opener.open('http://127.0.0.1:8080/blacknets')
