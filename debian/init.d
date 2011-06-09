#!/usr/bin/python
# -*- coding: utf-8 -*-
### BEGIN INIT INFO
# Provides:          antigfw
# Required-Start:    $network $local_fs $remote_fs
# Required-Stop:     $remote_fs
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Short-Description: Start and stop sshtunnel client daemon
### END INIT INFO

# Author: Shell Xu <shell909090@gmail.com>
'''
@date: 2011-04-07
@author: shell.xu
'''
import os
import sys
import imp
import signal
import pyinit
from os import path

runfile = pyinit.runfile('/var/run/antigfw.pid')

def load_config(pth_list):
    for pth in pth_list:
        if not path.exists(pth): continue
        mod = imp.load_source('config', pth)
        return mod.config

def ssh_runner(pre_pid, cfg):
    args = ['ssh', '-CNq', '-o', 'ServerAliveInterval=30', 
            '%s@%s' % (cfg['username'], cfg['sshhost']),
            '-p', cfg.get('sshport', 22), '-D', cfg.get('proxyport', 7778)]
    if 'sshprivfile' in cfg:
        args.extend(('-i', cfg['sshprivfile'],))
    return os.spawnv(os.P_NOWAIT, '/usr/bin/ssh', args)

def daemon_start():
    cfgs = load_config(['antigfw', '/etc/default/antigfw'])
    if cfgs is None:
        print 'antigfw config file not found'
        return
    runfile.chk_state(False)
    if pyinit.daemonized(True) > 0:
        print 'antigfw started.'
        return
    runfile.acquire()
    pyinit.watcher(ssh_runner, cfgs = cfgs)

def daemon_stop():
    for pid in runfile.getpids(): os.kill(pid, signal.SIGTERM)
    runfile.release()
    print 'antigfw stoped.'

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print '%s {start|stop|restart|force-reload}' % sys.argv[0]
        sys.exit(0)
    try:
        cmd = sys.argv[1].lower()
        if cmd == 'start': daemon_start()
        elif cmd == 'stop': daemon_stop()
        elif cmd == 'restart' or cmd == 'force-reload':
            daemon_stop()
            daemon_start()
    except Exception, e:
        print e
