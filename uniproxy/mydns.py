#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-09-27
@author: shell.xu
'''
import time, heapq, random, logging, conn
from gevent import socket, coros
import DNS

logger = logging.getLogger('dns')

def nslookup(sock, name):
    try:
        socket.inet_aton(name)
        return name
    except socket.error: pass
    stream = sock.makefile()
    m = DNS.Mpacker()
    qtype = DNS.Type.A
    tid = random.randint(0,65535)
    m.addHeader(tid, 0, DNS.Opcode.QUERY, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0)
    m.addQuestion(name, qtype, DNS.Class.IN)

    request = m.getbuf()
    stream.write(DNS.pack16bit(len(request)) + request)
    stream.flush()

    s = stream.read(2)
    if len(s) == 0: raise EOFError()
    count = DNS.unpack16bit(s)
    reply = stream.read(count)
    if len(reply) == 0: raise EOFError()

    u = DNS.Munpacker(reply)
    r = DNS.DnsResult(u, {})
    rslt = [i['data'] for i in r.answers if i['typename'] == 'A']
    logger.info('resolve %s to %s' % (name, str(rslt)))
    return rslt

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

class DNSServer(conn.Manager):
    DNSSERVER = '8.8.8.8'
    DNSPORT   = 53
    TIMEOUT   = 3600
    RETRY     = 3

    def __init__(self, get_conn_mgr, dnsserver=None, cachesize=512, max_conn=10):
        super(HttpManager, self).__init__(max_conn, 'dns')
        self.dnsserver = dnsserver or self.DNSSERVER
        self.cache, self.cachesize = ObjHeap(cachesize), cachesize
        self.get_conn_mgr = get_conn_mgr

    def gethostbyname(self, name):
        if name in self.cache:
            if time.time() - self.cache[name][0] <= self.TIMEOUT:
                return random.choice(self.cache[name][1])
            else: del self.cache[name]

        for i in xrange(self.RETRY):
            try:
                with self.smph:
                    with self.get_conn_mgr(False).get_socket(
                        self.dnsserver, self.DNSPORT) as sock:
                        r = nslookup(sock, name)
                        if not r: continue
                        self.cache[name] = (time.time(), r)
                        break
            except (EOFError, socket.error): pass

        r = self.cache.get(name)
        if r is None: return None
        else: return random.choice(r[1])

    def on_datagram(self, data):
        with self.smph:
            with self.get_conn_mgr(False).get_socket(self.dnsserver, self.DNSPORT) as sock:
                stream = sock.makefile()
                s = DNS.pack16bit(len(data))
                stream.write(s+data)
                stream.flush()

                s = stream.read(2)
                if len(s) == 0: raise EOFError()
                count = DNS.unpack16bit(s)
                reply = stream.read(count)
                if len(reply) == 0: raise EOFError()
        return reply

    def server(self, port=53):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('', port))
        logger.info('init DNS Server')

        while True:
            data, addr = sock.recvfrom(1024)
            logger.debug('data come in from %s' % str(addr))
            try:
                r = self.on_datagram(data)
                if r is None: continue
                sock.sendto(r, addr)
            except Exception, err: logger.exception(err)
