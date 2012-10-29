#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-10-29
@author: shell.xu
'''
import os, sys, time, socket, select, logging

sys.path.append('uniproxy')
from mydns import *

inquery = {}
DNSSERVER = '8.8.8.8'
TIMEOUT = 60
fakeset = set([
        '8.7.198.45', '37.61.54.158',
        '46.82.174.68', '59.24.3.173',
        '78.16.49.15', '93.46.8.89',
        '159.106.121.75', '203.98.7.65',
        '243.185.187.39'])

def on_query():
    data, addr = sock.recvfrom(1024)
    q = Record.unpack(data)
    if q.id not in inquery:
        inquery[q.id] = (addr, time.time())
        client.sendto(data, (DNSSERVER, 53))
    else: logging.warn('dns id %d is conflict.' % q.id)

def on_answer():
    data, addr = client.recvfrom(1024)
    r = Record.unpack(data)
    if r.id in inquery:
        addr, ti = inquery[r.id]
        if not get_ipaddrs(r): return
        sock.sendto(data, addr)
        del inquery[r.id]
    else: logging.warn('dns server return a record id %d but no one care.' % r.id)

def get_ipaddrs(r):
    ipaddrs = [rdata for name, type, cls, ttl, rdata in r.ans if type == TYPE.A]
    if not ipaddrs:
        logging.info('drop an empty dns response.')
    elif fakeset & set(ipaddrs):
        logging.info('drop %s for fakeset.' % ipaddrs)
    else: return ipaddrs

def on_idle():
    t = time.time()
    rlist = [k for k, v in inquery.iteritems() if t - v[1] > TIMEOUT]
    for k in rlist: del inquery[k]

def main():
    global sock, client
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('', 53))
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    logging.info('init dns server')

    poll = select.poll()
    fdmap = {sock.fileno(): on_query, client.fileno(): on_answer}
    for fd in fdmap.keys(): poll.register(fd, select.POLLIN)
    while True:
        try:
            for fd, ev in poll.poll(60): fdmap[fd]()
            on_idle()
        except Exception, err: logging.exception('unknown')

if __name__ == '__main__': main()
