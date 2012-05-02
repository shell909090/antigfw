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
import os, sys, signal, logging
from uniproxy import proxy_server, import_config, initlog
from os import path

logger = logging.getLogger('antigfw')

def daemonized():
    try:
        pid = os.fork()
        if pid > 0: return pid
    except OSError, e: sys.exit(1)
    os.chdir("/")
    os.setsid()
    os.umask(0)
    for i in xrange(0, 3): os.close(i)
    try:
        if os.fork() > 0: sys.exit(0)
    except OSError, e: sys.exit(1)
    return 0

def get_pid_status(pid):
    try: os.getsid(pid)
    except OSError: return False
    return True

def kill_stand(pids, timeout):
    t_start = time.time()
    for pid in pids: os.kill(pid, signal.SIGTERM)
    while (time.time() - t_start) < timeout and pids:
        pids = [pid for pid in pids if get_pid_status(pid)]
        time.sleep(1)
    for pid in pids: os.kill(pid, signal.SIGKILL)

class RunfileNotExistError(StandardError): pass
class RunfileExistError(StandardError): pass

class runfile(object):
    ERR_NOTEXIST = '%s not exist, daemon not started yet.'
    ERR_EXIST = '%s is exists.\nIf you really wanna run daemon, remove it first.'

    def __init__(self, filename, content = None):
        self.filename = filename

    def chk_state(self, in_run):
        b = path.exists(self.filename)
        if in_run and not b:
            raise RunfileNotExistError(self.ERR_NOTEXIST % self.filename)
        elif not in_run and b:
            raise RunfileExistError(self.ERR_EXIST % self.filename)

    def update(self, content):
        with open(self.filename, 'w') as fo: fo.write(content)

    def getpids(self):
        self.chk_state(True)
        with open(self.filename, 'r') as f:
            return [int(line.strip()) for line in f]

    def kill(self, sig):
        for pid in self.getpids(): os.kill(pid, sig)

    def kill_stand(self, timeout=5):
        kill_stand(self.getpids(), timeout)

    def getstatus(self):
        return all(map(get_pid_status, self.getpids()))

    def acquire(self):
        self.chk_state(False)
        self.update(str(os.getpid()))

    def release(self):
        self.chk_state(True)
        os.remove(self.filename)

    def __enter__(self): self.acquire()

    def __exit__(self, type, value, traceback): self.release()

class lockfile(object):

    def __init__(self, filename, share = False):
        self.filename = filename
        self.share = share

    def __enter__(self):
        self.file = open(self.filename, 'r')
        fcntl.flock(self.file.fileno(), fcntl.LOCK_SH if self.share else fcntl.LOCK_EX)

    def __exit__(self, type, value, traceback):
        fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
        self.file.close()

def watcher(*runners):
    clean_flag = False
    pids = dict([(runner, runner(0)) for runner in runners])
    def clean_up(signum, frame):
        if signum != signal.SIGTERM: return
        clean_flag = True
        kill_stand(pids.values(), 3)
    signal.signal(signal.SIGTERM, clean_up)
    while True:
        os.wait()
        if clean_flag: break
        for runner, pids in pids.iteritems():
            if get_pid_status(pid): continue
            time.sleep(1)
            pids[runner] = runner(pid)
    sys.exit(0)

def ssh_runner(cfgs):
    runners = []
    for i in cfgs:
        def real_runner(pre_pid):
            cfg = i.copy()
            args = ['ssh', '-CNq', '-o', 'ServerAliveInterval=30', 
                    '%s@%s' % (cfg['username'], cfg['sshhost']),]
            if 'sshport' in cfg:
                args.extend(('-p', cfg['sshport'],))
            if 'proxyport' in cfg:
                args.extend(('-D', cfg['proxyport'],))
            if 'sshprivfile' in cfg:
                args.extend(('-i', cfg['sshprivfile'],))
            return os.spawnv(os.P_NOWAIT, '/usr/bin/ssh', args)
        runners.append(real_runner)
    return runners

def uniproxy_runner(pre_pid):
    pid = os.fork()
    if pid > 0: return pid
    uniproxy.proxy_server('/etc/default/antigfw')
    sys.exit(0)

def main():
    runfile = runfile('/var/run/antigfw.pid')
    config = import_config('antigfw', '~/.antigfw', '/etc/default/antigfw')
    initlog(logging.INFO, getattr(config, 'logfile', None))

    def start():
        cfgs = config.servers
        try: runfile.chk_state(False)
        except RunfileExistError:
            print 'antigfw already started.'
            return
        if daemonized() > 0:
            print 'antigfw starting.'
            return
        runfile.acquire()
        watcher(uniproxy_runner, *ssh_runner(cfgs))

    def stop():
        try:
            runfile.kill_stand()
            runfile.release()
        except RunfileNotExistError: print 'antigfw not started yet.'
        print 'antigfw stoped.'

    def restart():
        stop()
        start()

    def help():
        print '%s {start|stop|restart|force-reload}' % sys.argv[0]

    cmds = {'start': start, 'stop': stop,
            'restart': restart, 'force-reload': restart}

    def inner(argv):
        if len(argv) <= 2: help()
        else: cmds.get(argv[1], help)()
    return inner

if __name__ == '__main__': main()(sys.argv)
