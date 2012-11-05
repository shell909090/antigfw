#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-10-18
@author: shell.xu
'''
import os, urllib2, unittest
from BeautifulSoup import BeautifulSoup

try: del os.environ['http_proxy']
except KeyError: pass
try: del os.environ['https_proxy']
except KeyError: pass

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

class TypeTest(unittest.TestCase):
    def test_chunk(self):
        s = BeautifulSoup(proxy_opener.open('http://wordpress.org//').read())
        self.assertTrue(s.title.string.find(u'WordPress') != -1)
    def test_length(self):
        s = BeautifulSoup(proxy_opener.open('http://www.twitter.com/').read())
        self.assertTrue(s.title.string.find(u'Twitter') != -1)
    def test_hasbody(self):
        s = BeautifulSoup(proxy_opener.open('http://www.dangdang.com/').read())
        self.assertTrue(s.title.string.find(u'当当网') != -1)

def main():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromModule(__import__('main')))
    suite.addTests(loader.loadTestsFromModule(__import__('mgr')))
    suite.addTests(loader.loadTestsFromModule(__import__('lru')))
    unittest.TextTestRunner(verbosity = 2).run(suite)

if __name__ == '__main__': main()
