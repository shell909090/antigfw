#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-10-18
@author: shell.xu
'''
import os, urllib2, unittest

proxy_handler = urllib2.ProxyHandler({
        'http': 'http://localhost:8080/', 'https': 'http://localhost:8080/'})
# proxy_auth_handler = urllib2.ProxyBasicAuthHandler()
# proxy_auth_handler.add_password('realm', 'host', 'username', 'password')
proxy_opener = urllib2.build_opener(proxy_handler)

class ProxyTest(unittest.TestCase):
    def test_ingfw_http(self):
        proxy_opener.open('http://www.sina.com.cn/')
    def test_ingfw_https(self):
        proxy_opener.open('https://www.cmbchina.com/')
    def test_gfw_http(self):
        proxy_opener.open('http://www.cnn.com/')
    def test_gfw_https(self):
        proxy_opener.open('https://www.facebook.com')

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

def main():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromModule(__import__('main')))
    suite.addTests(loader.loadTestsFromModule(__import__('lru')))
    unittest.TextTestRunner(verbosity = 2).run(suite)

if __name__ == '__main__': main()
