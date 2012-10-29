#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-10-16
@author: shell.xu
@remark: 用于将多个文件合并入一个脚本内，形成单一的上传文件
'''
import re, os, sys, getopt
from os import path

filepath = ['.',]

def findfile(filename):
    for p in filepath:
        f = path.join(p, filename)
        if path.exists(f): return f

include_re = re.compile('from (.*) import \*')
addpath_re = re.compile('sys\.path\.append\((.*)\)')
def server_compile(infile):
    for line in infile:
        mi = include_re.match(line)
        ma = addpath_re.match(line)
        if mi is not None:
            with open(findfile(mi.group(1) + '.py')) as fi:
                for line in server_compile(fi):
                    if line.startswith('#'): continue
                    yield line
            yield '\n'
        elif ma is not None:
            filepath.append(ma.group(1).strip('\''))
        else: yield line

def main():
    '''
    -h: help
    '''
    optlist, args = getopt.getopt(sys.argv[1:], 'h')
    optdict = dict(optlist)
    if '-h' in optdict:
        print '%s type output' % sys.argv[0]
        print main.__doc__
        return
    d = os.getcwd()
    if path.dirname(args[0]): os.chdir(path.dirname(args[0]))
    with open(path.basename(args[0])) as fi:
        data = ''.join(server_compile(fi))
    os.chdir(d)
    with open(args[1], 'w') as fo: fo.write(data)

if __name__ == '__main__': main()
