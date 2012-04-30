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
import os, sys, imp
import signal, logging
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

def watcher(functory, cfgs):
    clean_flag = False
    pids = [functory(0, cfg) for cfg in cfgs]
    def clean_up(signum, frame):
        if signum != signal.SIGTERM: return
        clean_flag = True
        kill_stand(pids, 3)
    signal.signal(signal.SIGTERM, clean_up)
    while True:
        os.wait()[0]
        if clean_flag: break
        for i, pid in enumerate(pids):
            if get_pid_status(pid): continue
            time.sleep(1)
            pids[i] = functory(pid, cfgs[i])
    sys.exit(0)

def import_config(*cfgs):
    d = {}
    for cfg in cfgs:
        try:
            with open(path.expanduser(cfg)) as fi:
                eval(compile(fi.read(), cfg, 'exec'), d)
        except OSError: pass
    return dict([(k, v) for k, v in d.iteritems() if not k.startswith('_')])

def ssh_runner(pre_pid, cfg):
    args = ['ssh', '-CNq', '-o', 'ServerAliveInterval=30', 
            '%s@%s' % (cfg['username'], cfg['sshhost']),]
    if 'sshport' in cfg:
        args.extend(('-p', cfg['sshport'],))
    if 'proxyport' in cfg:
        args.extend(('-D', cfg['proxyport'],))
    if 'sshprivfile' in cfg:
        args.extend(('-i', cfg['sshprivfile'],))
    return os.spawnv(os.P_NOWAIT, '/usr/bin/ssh', args)

def main():
    runfile = runfile('/var/run/antigfw.pid')
    config = import_config('antigfw', '~/.antigfw', '/etc/default/antigfw')
    if hasattr(config, 'logfile') and config.logfile:
        handler = logging.FileHandler(config.logfile)
    else: handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    def start():
        cfgs = config.servers
        runfile.chk_state(False)
        if daemonized() > 0:
            print 'antigfw started.'
            return
        runfile.acquire()
        watcher(ssh_runner, cfgs = cfgs)

    def stop():
        try:
            runfile.kill_stand()
            runfile.release()
        except RunfileNotExistError: pass
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
