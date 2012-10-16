#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-10-16
@author: shell.xu
@remark: 用于将多个文件合并入一个脚本内，形成单一的上传文件
'''
import re, sys, getopt

include_re = re.compile('from (.*) import \*')
def server_compile(infile):
    for line in infile:
        m = include_re.match(line)
        if m is not None: 
            with open(m.group(1) + '.py') as fi:
                for line in server_compile(fi):
                    if line.startswith('#'): continue
                    yield line
            yield '\n'
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
    with open(args[0]) as fi:
        data = ''.join(server_compile(fi))
    with open(args[1], 'w') as fo: fo.write(data)

if __name__ == '__main__': main()
