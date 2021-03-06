#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-09-29
@author: shell.xu
'''
import sys, time, heapq, random, getopt, logging, cStringIO, gevent
from mydns import *
from contextlib import contextmanager
from gevent import socket, queue

logger = logging.getLogger('dnsserver')

class ObjHeap(object):
    ''' 使用lru算法的对象缓存容器，感谢Evan Prodromou <evan@bad.dynu.ca>。
    thx for Evan Prodromou <evan@bad.dynu.ca>. '''
    MAXSEQ = 0x100000000

    class __node(object):
        def __init__(self, k, v, f): self.k, self.v, self.f = k, v, f
        def __cmp__(self, o): return self.f > o.f

    def __init__(self, size):
        self.size = size
        self.clean()

    def clean(self):
        self.f, self.__dict, self.__heap = 0, {}, []

    def getseq(self):
        if self.f >= self.MAXSEQ:
            self.f = 1
            for n in self.__heap: n.f = 0
        else: self.f += 1
        return self.f

    def __len__(self): return len(self.__dict)
    def __contains__(self, k): return self.__dict.has_key(k)

    def __setitem__(self, k, v):
        if self.__dict.has_key(k):
            n = self.__dict[k]
            n.v, n.f = v, self.getseq()
        elif len(self.__heap) < self.size:
            n = self.__node(k, v, self.getseq())
            self.__heap.append(n)
            self.__dict[k] = n
        else:
            heapq.heapify(self.__heap)
            try:
                while len(self.__heap) > self.size:
                    del self.__dict[heapq.heappop(self.__heap).k]
                n = self.__node(k, v, self.getseq())
                del self.__dict[heapq.heappushpop(self.__heap, n).k]
                self.__dict[k] = n
            except KeyError: self.clean()

    def __getitem__(self, k):
        n = self.__dict[k]
        n.f = self.getseq()
        return n.v

    def get(self, k):
        n = self.__dict.get(k)
        if n is None: return None
        n.f = self.getseq()
        return n.v

    def __delitem__(self, k):
        n = self.__dict[k]
        self.__heap.remove(n)
        del self.__dict[k]
        return n.v

    def __iter__(self):
        c = self.__heap[:]
        while len(c): yield heapq.heappop(c).k

class DNSServer(object):
    DNSSERVER = '8.8.8.8'
    DNSPORT   = 53
    TIMEOUT   = 3600
    RETRY     = 3

    def __init__(self, dnsserver, cachesize=512, timeout=30):
        self.dnsserver = dnsserver or self.DNSSERVER
        self.cache, self.cachesize = ObjHeap(cachesize), cachesize
        self.timeout = timeout
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.fakeset = set()
        self.inquery = {}
        self.gr = gevent.spawn(self.receiver)
        self.srv = None

    def runserver(self, dnsport=None):
        self.srv = gevent.spawn(self.server, dnsport)

    def stop(self):
        if self.srv: self.srv.kill()
        self.gr.kill()

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

    def get_ipaddrs(self, r):
        ipaddrs = [rdata for name, type, cls, ttl, rdata in r.ans if type == TYPE.A]
        if not ipaddrs:
            logger.info('drop an empty dns response.')
            return
        if self.fakeset and self.fakeset & set(ipaddrs):
            logger.info('drop %s in fakeset.' % ipaddrs)
            return
        ttls = [ttl for name, type, cls, ttl, rdata in r.ans if type == TYPE.A]
        return ipaddrs, ttls[0] * 60 if ttls else self.TIMEOUT

    def gethostbyname(self, name):
        try:
            socket.inet_aton(name)
            return name
        except socket.error: pass

        if name in self.cache:
            if time.time() <= self.cache[name][0]:
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

    def query(self, name, type=TYPE.A):
        q = mkquery((name, type))
        while q.id in self.inquery: q = mkquery((name, type))
        logger.debug('request dns %s with id %d' % (name, q.id))
        with self.with_queue(q.id) as qp:
            self.sock.sendto(q.pack(), (self.dnsserver, self.DNSPORT))
            for i in xrange(self.RETRY):
                try:
                    r = qp.get(timeout=self.timeout)
                    logger.debug('get response with id: %d' % r.id)
                    ipaddrs, ttl = self.get_ipaddrs(r)
                    self.cache[name] = (time.time() + ttl, ipaddrs)
                    return
                except (EOFError, socket.error): continue
                except queue.Empty: return

    def receiver(self):
        while True:
            try:
                while True:
                    d = self.sock.recvfrom(2048)[0]
                    r = Record.unpack(d)
                    if not self.get_ipaddrs(r): continue
                    if r.id not in self.inquery:
                        logger.warn('got a record not in query\n')
                        for line in r.show(): logger.warn(line)
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
                    self.on_datagram(data, sock, addr)
            except Exception, err: logger.exception(err)

class TCPDNSServer(DNSServer):

    def __init__(self, dnsserver, cmanager=None, cachesize=512, timeout=30):
        self.dnsserver = dnsserver or self.DNSSERVER
        self.cache, self.cachesize = ObjHeap(cachesize), cachesize
        self.timeout = timeout
        self.fakeset = set()
        self.cmanager = cmanager
        if self.cmanager is None: self.cmanager = conn.DirectManager(self.dns)
    
    def query(self, name, type=TYPE.A):
        q = mkquery((name, type))
        while q.id in self.inquery: q = mkquery((name, type))
        logger.debug('request dns %s with id %d in tcp' % (name, q.id))

        with self.cmanager.socket() as sock:
            stream = sock.makefile()

            data = q.pack()
            stream.write(struct.pack('!H', len(data)) + data)
            stream.flush()
            s = stream.read(2)
            if len(s) == 0: raise EOFError()
            count = struct.unpack('!H', s)[0]
            reply = stream.read(count)
            if len(reply) == 0: raise EOFError()

            r = Record.unpack(reply)
            ips = self.get_ipaddrs(r)
            if ips is None: raise Exception('get fake ip in tcp mode?')
            ipaddrs, ttl = ips
            self.cache[name] = (time.time() + ttl, ipaddrs)

    def on_datagram(self, data, sock, addr):
        q = Record.unpack(data)

        with self.cmanager.socket() as sock:
            stream = sock.makefile()

            s = struct.pack('!H', len(data))
            stream.write(s+data)
            stream.flush()
            s = stream.read(2)
            if len(s) == 0: raise EOFError()
            count = struct.unpack('!H', s)[0]
            reply = stream.read(count)
            if len(reply) == 0: raise EOFError()

            sock.sendto(reply, d)
