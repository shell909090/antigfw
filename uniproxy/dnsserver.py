#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-09-29
@author: shell.xu
'''
import sys, time, heapq, random, getopt, logging, gevent
from mydns import *
from contextlib import contextmanager
from gevent import socket, queue, timeout

logger = logging.getLogger('dnsserver')

class ObjHeap(object):
    ''' 使用lru算法的对象缓存容器，感谢Evan Prodromou <evan@bad.dynu.ca>。
    thx for Evan Prodromou <evan@bad.dynu.ca>. '''

    class __node(object):
        def __init__(self, k, v, f): self.k, self.v, self.f = k, v, f
        def __cmp__(self, o): return self.f > o.f

    def __init__(self, size):
        self.size, self.f = size, 0
        self.__dict, self.__heap = {}, []

    def __len__(self): return len(self.__dict)
    def __contains__(self, k): return self.__dict.has_key(k)

    def __setitem__(self, k, v):
        if self.__dict.has_key(k):
            n = self.__dict[k]
            n.v = v
            self.f += 1
            n.f = self.f
            heapq.heapify(self.__heap)
        else:
            while len(self.__heap) >= self.size:
                del self.__dict[heapq.heappop(self.__heap).k]
                self.f = 0
                for n in self.__heap: n.f = 0
            n = self.__node(k, v, self.f)
            self.__dict[k] = n
            heapq.heappush(self.__heap, n)

    def __getitem__(self, k):
        n = self.__dict[k]
        self.f += 1
        n.f = self.f
        heapq.heapify(self.__heap)
        return n.v

    def get(self, k):
        n = self.__dict.get(k)
        if n is None: return None
        self.f += 1
        n.f = self.f
        heapq.heapify(self.__heap)
        return n.v

    def __delitem__(self, k):
        n = self.__dict[k]
        del self.__dict[k]
        self.__heap.remove(n)
        heapq.heapify(self.__heap)
        return n.v

    def __iter__(self):
        c = self.__heap[:]
        while len(c): yield heapq.heappop(c).k
        raise StopIteration

class DNSServer(object):
    DNSSERVER = '8.8.8.8'
    DNSPORT   = 53
    TIMEOUT   = 3600
    RETRY     = 3

    def __init__(self, dnsserver=None, cachesize=512, timeout=30):
        self.dnsserver = dnsserver or self.DNSSERVER
        self.cache, self.cachesize = ObjHeap(cachesize), cachesize
        self.timeout = timeout
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.fakeset = set()
        self.inquery = {}
        gevent.spawn(self.receiver)

    def empty(self): self.fakeset = set()

    def load(self, stream):
        for line in stream:
            if line.startswith('#'): continue
            self.fakeset.add(line.strip())

    def loadfile(self, filename):
        openfile = open
        if filename.endswith('.gz'):
            import gzip
            openfile = gzip.open
        try:
            with openfile(filename) as fi: self.load(fi)
        except (OSError, IOError): return False

    def loadlist(self, filelist):
        for f in filelist: self.loadfile(f)

    def save(self, stream):
        for i in list(self.fakeset): stream.write(i+'\n')

    def savefile(self, filepath):
        openfile = open
        if filepath.endswith('.gz'):
            import gzip
            openfile = gzip.open
        try:
            with openfile(filepath, 'w+') as fo: self.save(fo)
        except (OSError, IOError): return False

    def gethostbyname(self, name):
        try:
            socket.inet_aton(name)
            return name
        except socket.error: pass

        if name in self.cache:
            if time.time() - self.cache[name][0] <= self.TIMEOUT:
                return random.choice(self.cache[name][1])
            else: del self.cache[name]

        self.query(name)
        r = self.cache.get(name)
        if r is None: return None
        else: return random.choice(r[1])

    @contextmanager
    def with_queue(self, id):
        qp = queue.Queue()
        logger.debug('add id %d' % id)
        self.inquery[id] = lambda r, d: qp.put(r)
        try: yield qp
        finally: del self.inquery[id]
        logger.debug('del id %d' % id)

    def get_result(self, qp):
        for i in xrange(self.RETRY):
            try:
                r = qp.get(timeout=self.timeout)
                logger.debug('get response with id: %d' % r.id)
                ipaddrs = [rdata for name, type, cls, ttl, rdata in r.ans if type == TYPE.A]
                if self.fakeset and any(map(lambda ip: ip in self.fakeset, ipaddrs)):
                    logger.info('drop %s in fakeset.' % ipaddrs)
                    continue
                return ipaddrs
            except (EOFError, socket.error): continue
            except timeout.Timeout: return

    def query(self, name, type=TYPE.A):
        q = mkquery((name, type))
        while q.id in self.inquery: q = mkquery((name, type))
        logger.debug('request dns %s with id %d' % (name, q.id))
        with self.with_queue(q.id) as qp:
            self.sock.sendto(q.pack(), (self.dnsserver, self.DNSPORT))
            ipaddrs = self.get_result(qp)
        if ipaddrs: self.cache[name] = (time.time(), ipaddrs)

    def receiver(self):
        while True:
            try:
                while True:
                    d = self.sock.recvfrom(1024)[0]
                    r = Record.unpack(d)
                    if r.id not in self.inquery:
                        logger.warn('dns server got a record but don\'t know who care it\'s id')
                        logger.debug('this record id is: %d' % r.id)
                    else: self.inquery[r.id](r, d)
            except Exception, err: logger.exception(err)

    def on_datagram(self, data, sock, addr):
        q = Record.unpack(data)
        if q.id in self.inquery:
            logger.warn('dns id %d conflict.' % q.id)
            return

        # TODO: timeout!
        def sendback(r, d):
            assert r.id==q.id
            ipaddrs = [rdata for name, type, cls, ttl, rdata in r.ans if type == TYPE.A]
            if self.fakeset and any(map(lambda ip: ip in self.fakeset, ipaddrs)):
                logger.info('drop %s in fakeset.' % ipaddrs)
                return
            sock.sendto(d, addr)
            del self.inquery[q.id]
        self.inquery[q.id] = sendback
        self.sock.sendto(data, (self.dnsserver, self.DNSPORT))

    def server(self, port=53):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('', port))
        logger.info('init DNS Server')

        while True:
            try:
                while True:
                    data, addr = sock.recvfrom(1024)
                    logger.debug('data come in from %s' % str(addr))
                    self.on_datagram(data, sock, addr)
            except Exception, err: logger.exception(err)

def main():
    optlist, args = getopt.getopt(sys.argv[1:], 'df')
    optdict = dict(optlist)
    dnsfake = ['../dnsfake']
    if '-f' in optdict: dnsfake.insert(0, optdict['-f'])
    dns = DNSServer()
    dns.loadlist(dnsfake)
    if '-d' in optdict:
        dns.server()
    else:
        for arg in args: print arg, dns.gethostbyname(arg)

if __name__ == '__main__': main()
