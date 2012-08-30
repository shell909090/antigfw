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
import os, sys, time, signal, logging
from os import path

def import_config(*cfgs):
    d = {}
    for cfg in reversed(cfgs):
        try:
            with open(path.expanduser(cfg)) as fi:
                eval(compile(fi.read(), cfg, 'exec'), d)
        except (OSError, IOError): pass
    return dict([(k, v) for k, v in d.iteritems() if not k.startswith('_')])

def initlog(lv, logfile=None):
    rootlog = logging.getLogger()
    if logfile: handler = logging.FileHandler(logfile)
    else: handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            '%(asctime)s,%(msecs)03d %(name)s[%(levelname)s]: %(message)s',
            '%H:%M:%S'))
    rootlog.addHandler(handler)
    rootlog.setLevel(lv)

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
    logger.info('daemonized finish')
    return 0

def get_pid_status(pid):
    try: os.getsid(pid)
    except OSError: return False
    return True

def kill_stand(pids, timeout):
    t_start = time.time()
    logger.debug('try stop.')
    for pid in pids:
        try: os.kill(pid, signal.SIGTERM)
        except OSError: pass
    while (time.time() - t_start) < timeout and pids:
        pids = [pid for pid in pids if get_pid_status(pid)]
        time.sleep(1)
    logger.debug('try kill %d.' % len(pids))
    for pid in pids:
        try: os.kill(pid, signal.SIGKILL)
        except OSError: pass
    logger.debug('kill sent.')

class RunfileNotExistError(StandardError): pass
class RunfileExistError(StandardError): pass

class RunFile(object):
    ERR_NOTEXIST = '%s not exist, daemon not started yet.'
    ERR_EXIST = '%s is exists.\nIf you really wanna run daemon, remove it first.'

    def __init__(self, filename): self.bind(filename)
    def bind(self, filename): self.filename = filename

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

    def __init__(self, filename, share=False):
        self.filename, self.share = filename, share

    def __enter__(self):
        self.file = open(self.filename, 'r')
        fcntl.flock(self.file.fileno(),
                    fcntl.LOCK_SH if self.share else fcntl.LOCK_EX)

    def __exit__(self, type, value, traceback):
        fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
        self.file.close()

def watcher(*runners):
    clean_flag = False
    pids = dict([(runner, runner(0)) for runner in runners])
    def clean_up(signum, frame):
        if signum != signal.SIGTERM: return
        logger.info('signal TERM, start to stop childs')
        clean_flag = True
        kill_stand(pids.values(), 3)
    signal.signal(signal.SIGTERM, clean_up)
    while True:
        os.wait()
        if clean_flag: break
        for runner, pid in pids.iteritems():
            if get_pid_status(pid): continue
            pids[runner] = runner(pid)
        time.sleep(1)
    logger.info('system exit')

def ssh_runner(cfg):
    def real_runner(pre_pid):
        if pre_pid: logger.info('prior ssh stopped, pid %d' % pre_pid)
        args = ['ssh', '-CNq', '-o', 'ServerAliveInterval=30', 
                '%s@%s' % (cfg['username'], cfg['sshhost']),]
        if 'sshport' in cfg: args.extend(('-p', cfg['sshport'],))
        if 'sockport' in cfg: args.extend(('-D', str(cfg['sockport']),))
        if 'listenport' in cfg:
            lopt = '%d:localhost:%d' % (cfg['listenport'][0], cfg['listenport'][1])
            args.extend(('-L', lopt,))
        if 'sshprivfile' in cfg: args.extend(('-i', cfg['sshprivfile'],))
        pid = os.spawnv(os.P_NOWAIT, '/usr/bin/ssh', args)
        logger.info('ssh starting pid %d with cmdline "%s"' % (
                pid, ' '.join(args)))
        return pid
    return real_runner

def uniproxy_runner(pre_pid):
    pid = os.fork()
    if pid > 0: return pid
    from uniproxy import main
    main('antigfw', '~/.antigfw', '/etc/default/antigfw')
    sys.exit(0)

def proccmd():
    config = {}
    runfile = RunFile(None)

    def start():
        if not config.get('daemon', False):
            print 'not start due to config.daemon not set'
            return
        try: runfile.chk_state(False)
        except RunfileExistError:
            print 'antigfw already started.'
            return
        if daemonized() > 0:
            print 'antigfw starting.'
            return
        runfile.acquire()
        try:
            try:
                runners = []
                if config.get('autossh', None):
                    runners.extend([ssh_runner(cfg) for cfg in config['sshs']])
                if config.get('uniproxy', True): runners.append(uniproxy_runner)
                watcher(*runners)
            except: logger.exception('unknown')
        finally: runfile.release()

    def stop():
        try:
            runfile.kill_stand()
            runfile.release()
        except RunfileNotExistError: print 'kill force.'
        print 'antigfw stoped.'

    def restart():
        stop()
        start()

    def help():
        print '%s {start|stop|restart|force-reload}' % sys.argv[0]

    cmds = {'start': start, 'stop': stop,
            'restart': restart, 'force-reload': restart}

    def init(*cfgs):
        if cfgs: config.update(import_config(*cfgs))
        initlog(getattr(logging, config.get('loglevel', 'WARNING')),
                config.get('logfile', None))
        runfile.bind(config.get('pidfile', '/var/run/antigfw.pid'))

    def handler(argv):
        if not argv: help()
        else: cmds.get(argv[0], help)()
    def final(): pass
    return init, handler, final

def main():
    init, handler, final = proccmd()
    init('antigfw', '~/.antigfw', '/etc/default/antigfw')
    try: handler(sys.argv[1:])
    finally: final()

if __name__ == '__main__': main()
