#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-04-26
@author: shell.xu
'''
import sys, logging

__all__ = ['DomainFilter']
logger = logging.getLogger('filter')

class DomainFilter(object):

    def __init__(self): self.domains = {}
    def empty(self): self.domains = {}

    def add(self, domain):
        doptr, chunk, domain = self.domains, domain.split('.'), domain.lower()
        for c in reversed(chunk):
            if len(c.strip()) == 0: continue
            if c not in doptr or doptr[c] is None: doptr[c] = {}
            lastptr, doptr = doptr, doptr[c]
        if len(doptr) == 0: lastptr[c] = None

    def remove(self, domain):
        doptr, stack, chunk = self.domains, [], domain.split('.')
        for c in reversed(chunk):
            if len(c.strip()) == 0: raise LookupError()
            if doptr is None: return False
            stack.append(doptr)
            if c not in doptr: return False
            doptr = doptr[c]
        for doptr, c in zip(reversed(stack), chunk):
            if doptr[c] is None or len(doptr[c]) == 0: del doptr[c]
        return True

    def __getitem__(self, domain):
        doptr, chunk = self.domains, domain.split('.')
        for c in reversed(chunk):
            if len(c.strip()) == 0: continue
            if c not in doptr: return False
            doptr = doptr[c]
            if doptr is None: break
        return doptr
    def __contains__(self, domain): return self.__getitem__(domain) is None

    def getlist(self, d = None, s = ''):
        if d is None: d = self.domains
        for k, v in d.items():
            t = '%s.%s' %(k, s)
            if v is None: yield t.strip('.')
            else:
                for i in self.getlist(v, t): yield i

    def show(self, d = None, s = 0):
        if d is None: d = self.domains
        for k, v in d.items():
            yield '  '*s + k
            if v is not None:
                for i in self.show(v, s + 1): yield i

    def load(self, stream):
            for line in stream:
                if line.startswith('#'): continue
                self.add(line.strip().lower())

    def loadfile(self, filepath):
        openfile = open
        if filepath.endswith('.gz'):
            import gzip
            openfile = gzip.open
        try:
            with openfile(filepath, 'r') as fi: self.load(fi)
        except (OSError, IOError): return False

    def save(self, stream):
        for line in sorted(self.getlist()): stream.write(line+'\n')

    def savefile(self, filepath):
        openfile = open
        if filepath.endswith('.gz'):
            import gzip
            openfile = gzip.open
        try:
            with openfile(filepath, 'w+') as fo: self.save(fo)
        except (OSError, IOError): return False

def main():
    filter = DomainFilter()
    filter.loadfile(sys.argv[1])
    for i in sys.argv[2:]: print '%s: %s' % (i, i in filter)

if __name__ == '__main__': main()
