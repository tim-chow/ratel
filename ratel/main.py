import sys
import os
import time
import threading
import optparse
import signal

from .util import get_server_socket
from .event_loop import EventLoop

class ReadPipeThread(threading.Thread):
    def __init__(self, r_fd, *a, **kw):
        threading.Thread.__init__(self, *a, **kw)
        self._r_fd = r_fd

    def run(self):
        while True:
            try:
                self._r_fd.readline()
            except IOError:
                break

class Worker:
    def __init__(self, r_fd, server_socket, commandclass):
        # to consume the data in pipe
        self._thread = ReadPipeThread(r_fd)
        self._thread.setDaemon(True)
        self._thread.start()
        self._handle_signal()

        self._r_fd = r_fd
        self._server_socket = server_socket
        self._event_loop = EventLoop(server_socket). \
            register_command_class(commandclass)

    def _on_sig_int(self, sn, fo):
        print "worker: %s received signal: %s" %(os.getpid(), sn)
        # XXX: should close self._r_fd
        self._event_loop.stop()

    def _handle_signal(self):
        signal.signal(signal.SIGINT, self._on_sig_int)
        signal.signal(signal.SIGUSR1, self._on_sig_int)
        signal.signal(signal.SIGUSR2, self._on_sig_int)

    def worker_logic(self):
        self._event_loop.start()

class Entry:
    def __init__(self, options):
        self._options = options
        self._pipe_to_pid = {}
        self._poll_timeout = 0.01
        self._poll_state = 1 # 1 check, 2 pause, 3 stop
        self._server_socket = get_server_socket(
            self._options.host,
            self._options.port,
            self._options.backlog)

    def close(self):
        if hasattr(self, "_server_socket") and \
            hasattr(self._server_socket, "close") and \
            callable(self._server_socket.close):
            try:
                print "closing server socket"
                self._server_socket.close()
            except IOError as ex:
                print ex

    def __del__(self):
        self.close()

    def spawn_one(self):
        r, w = os.pipe()
        r_fd = os.fdopen(r, "r")
        w_fd = os.fdopen(w, "w")

        pid = os.fork()
        if pid > 0:
            r_fd.close()
            self._pipe_to_pid[w_fd] = pid
            return

        #child process
        w_fd.close()
        Worker(r_fd, self._server_socket,
            self._options.commandclass).worker_logic()
        os._exit(0)

    # reload
    def _on_sig_int(self, sn, fo):
        print "master: %s received signal: %s" %(os.getpid(), sn)
        self._poll_state = 2

    # stop
    def _on_sig_usr2(self, sn, fo):
        print "master: %s received signal: %s" %(os.getpid(), sn)
        self._poll_state = 3

    def _handle_signal(self):
        signal.signal(signal.SIGINT, self._on_sig_int)
        signal.signal(signal.SIGUSR1, self._on_sig_int)
        signal.signal(signal.SIGUSR2, self._on_sig_usr2)

    def _stop(self, w_fds=None):
        print "stopping"
        if not w_fds:
            w_fds = self._pipe_to_pid.keys()
            pids = self._pipe_to_pid.values()
        else:
            pids = [pid for w_fd, pid in
                self._pipe_to_pid.items() if w_fd in w_fds]

        for w_fd in w_fds:
            try:
                w_fd.close()
            except IOError as ex: 
                print "IOError: " + str(ex)

            try:
                pid = self._pipe_to_pid.pop(w_fd)
                os.kill(pid, signal.SIGINT)
            except OSError as ex:
                print "OSError: " + str(ex)

        for pid in pids:
            print "os.waitpid(%s):" % pid
            print os.waitpid(pid, 0)
        print "stopped"

    def _reload(self):
        print "reloading"
        w_fds = self._pipe_to_pid.keys()

        # first of all, spawn new workers
        for _ in range(self._options.worker):
            self.spawn_one()
        # secondly, kill all old workers
        self._stop(w_fds)

        self._poll_state = 1
        print "reloaded"

    def execute(self):
        for _ in range(self._options.worker):
            self.spawn_one()
        print "master is:", os.getpid()
        print "workers:", self._pipe_to_pid.values()

        self._handle_signal()

        while True:
            time.sleep(self._poll_timeout)
            if self._poll_state == 2:
                self._reload()
                continue
            if self._poll_state == 3:
                self._stop()
                self.close()
                break

            w_fds = self._pipe_to_pid.keys()
            for w_fd in w_fds:
                try:
                    w_fd.write("ping\n")
                    w_fd.flush()
                except IOError:
                    pid = self._pipe_to_pid.pop(w_fd)
                    print "%d is dead, respawn one worker" % pid
                    self.spawn_one()

def handle_command_line_options():
    usage = "%prog options"
    parser = optparse.OptionParser(usage)

    parser.add_option("-w", "--worker", type=int,
        dest="worker",
        help="worker count")
    parser.add_option("-H", "--host", type=str,
        dest="host", default="127.0.0.1",
        help="ip address to listen on")
    parser.add_option("-p", "--port", type=int,
        dest="port", 
        help="port to listen on")
    parser.add_option("-b", "--backlog", type=int,
        dest="backlog", default=5,
        help="listen backlog")
    parser.add_option("-P", "--path", type=str,
        dest="pythonpath",
        help="Python path")
    parser.add_option("-c", "--command", type=str,
        dest="commandclass",
        help="command class")

    options, args = parser.parse_args()
    if not options.worker:
        parser.error("invalid worker count")
    if not options.port:
        parser.error("invalid port")
    if options.pythonpath:
        sys.path.extend(options.pythonpath.split(","))
    if not options.commandclass:
        parser.error("invalid command class")
    package_name, class_name = options.commandclass. \
        split(":")
    options.commandclass = getattr(__import__(package_name),
        class_name)

    return options, args

def main():
    options, _ = handle_command_line_options()
    Entry(options).execute()

