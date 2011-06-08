#!/usr/bin/python
# -*- coding: utf-8 -*-
### BEGIN INIT INFO
# Provides:          antigfw
# Required-Start:    $network $local_fs
# Required-Stop:
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Short-Description: Start and stop sshtunnel client daemon
### END INIT INFO

# Author: Shell Xu <shell909090@gmail.com>
'''
@date: 2011-04-07
@author: shell.xu
'''
from __future__ import with_statement
import os
import sys
import imp
import signal
import threading
from os import path

PID_PATH = '/var/run/antigfw.pid'
cfgs = []

class RunCfg(threading.Thread):
    default_setting = {'proxyport':7778, 'sshport':22}

    def __init__(self, cfg):
        super(RunCfg, self).__init__()
        new_default = self.default_setting.copy()
        new_default.update(cfg)
        self.cfg = new_default
        self.pid = 0

    def run_ssh(self):
        args = ['ssh', '-CNq', '-o', 'ServerAliveInterval=30', 
                '%s@%s' % (self.cfg['username'], self.cfg['sshhost']),
                '-p', self.cfg['sshport'], '-D', self.cfg['proxyport']]
        if 'sshprivfile' in self.cfg:
            args.extend(('-i', self.cfg['sshprivfile'],))
        return os.spawnv(os.P_NOWAIT, '/usr/bin/ssh', args)

    def run(self):
        while True:
            self.pid = self.run_ssh()
            update_pid()
            os.waitpid(self.pid, 0)

def load_config(pth_list):
    for pth in pth_list:
        if not path.exists(pth): continue
        mod = imp.load_source('config', pth)
        return [RunCfg(i) for i in mod.config]
    return None

def daemonized():
    try:
        if os.fork() > 0: sys.exit(0)
    except OSError, e: sys.exit(1)
    os.chdir("/")
    os.setsid()
    os.umask(0)
    for i in xrange(0, 3): os.close(i)
    try:
        if os.fork() > 0: sys.exit(0)
    except OSError, e: sys.exit(1)

update_lock = threading.Lock()
def update_pid():
    with update_lock:
        with open(PID_PATH, 'w') as f:
            f.write('%d\n' % os.getpid())
            for c in cfgs: f.write('%d\n' % c.pid)

def daemon_start():
    global cfgs
    if path.exists(PID_PATH):
	print '%s is exists.\nIf you really wanna run daemon, remove it first.' % PID_PATH 
	return
    daemonized()
    cfgs = load_config(['antigfw', '/etc/default/antigfw'])
    if cfgs is None: print 'antigfw config file not found'
    else:
        for c in cfgs: c.start()

def daemon_stop():
    if not path.exists(PID_PATH): return
    with open(PID_PATH, 'r') as f:
        for line in f: os.kill(int(line.strip()), signal.SIGTERM)
    os.remove(PID_PATH)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print '%s {start|stop|restart}' % sys.argv[0]
    elif sys.argv[1].lower() == 'start': daemon_start()
    elif sys.argv[1].lower() == 'stop': daemon_stop()
    elif sys.argv[1].lower() == 'restart':
        daemon_stop()
        daemon_start()
