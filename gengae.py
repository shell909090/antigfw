#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-10-28
@author: shell.xu
'''
import re, os, sys, shutil
from os import path

def genapp(srcpath, dstpath):
    import sc
    d = os.getcwd()
    os.chdir(path.dirname(srcpath))
    with open(path.basename(srcpath)) as fi:
        data = ''.join(sc.server_compile(fi))
    os.chdir(d)
    with open(dstpath, 'w') as fo: fo.write(data)

re_tmpl = re.compile('<%(.*?)%>')
def template(s, d):
    return re_tmpl.sub(lambda m: str(eval(m.group(1), globals(), d)), s)

def gencfg(srcpath, dstpath):
    with open(srcpath) as fi: data = fi.read()
    data = template(data, {"youappid": raw_input("youappid: ")})
    with open(dstpath, 'w') as fo: fo.write(data)

def main():
    if path.exists(sys.argv[2]): shutil.rmtree(sys.argv[2])
    os.mkdir(sys.argv[2])
    genapp(path.join(sys.argv[1], 'wsgi.py'),
           path.join(sys.argv[2], 'wsgi.py'))
    shutil.copyfile(path.join(sys.argv[1], 'robots.txt'),
                    path.join(sys.argv[2], 'robots.txt'))
    gencfg(path.join(sys.argv[1], 'app.yaml'),
           path.join(sys.argv[2], 'app.yaml'))
    

if __name__ == '__main__': main()
