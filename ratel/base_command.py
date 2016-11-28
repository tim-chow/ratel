import os
import time
import struct

from .util import SafeModeMetaClass

class BaseCommand:
    __metaclass__ = SafeModeMetaClass

    def __init__(self, conn, socket_event):
        self._conn = conn
        self._socket_event = socket_event
        self._last_recv_time = time.time()
        self._last_send_time = time.time()
        self._event = socket_event.READ

    def before_poll(self):
        pass

    def after_poll(self):
        pass

    def get_event(self):
        return self._event

    def on_shutdown(self):
        pass

    def on_peer_close(self, event):
        pass

    def on_close(self):
        pass

    def on_connected(self):
        pass

    def before_read_data(self):
        pass

    def after_read_data(self):
        pass

    def before_write_data(self):
        pass

    def after_write_data(self):
        pass

    def read_data_ok(self):
        pass

    def write_data_ok(self):
        pass

    def recv(self, n):
        tmp = ""
        while True:
            tmp = tmp + self._conn.recv(n-len(tmp))
            self._last_recv_time = time.time()
            if len(tmp) < n:
                yield False, tmp
                continue
            yield True, tmp
            break

    def send(self, data):
        tmp = 0
        while True:
            tmp = tmp + self._conn.send(data[tmp:])
            self._last_send_time = time.time()
            if tmp < len(data):
                yield False, tmp
                continue 
            yield True, tmp
            break

    def turn_to_read(self):
        self._event = self._socket_event.READ

    def turn_to_write(self):
        self._event = self._socket_event.WRITE

    def turn_to_stop(self):
        self._event = self._socket_event.STOP

class RecordCommand(BaseCommand):
    def __init__(self, *a, **kw):
        BaseCommand.__init__(self, *a, **kw)

        self._header = "!I"
        self._header_size = struct.calcsize(self._header)
        self._raw_request = ""
        self.turn_to_read()

        self.on_data_in = self._read_and_eval()
        self.on_data_out = self._write_response()

    def _read_and_eval(self):
        for status, data in self.recv(self._header_size):
            if status == False:
                yield
                continue
            length = struct.unpack(self._header, data)[0]
            break
        for status, data in self.recv(length):
            if status == False:
                yield
                continue
            self._raw_request = data
            break
        self.turn_to_write()

    def _write_response(self):
        result = struct.pack(self._header, len(self._raw_request)) + \
            self._raw_request

        for status, count in self.send(result):
            if status == True:
                break
            yield
        self.turn_to_stop()

    def _getpeername(self):
        return str(self._conn.getpeername())

    def on_shutdown(self):
        print "on_shutdown: %s" % self._getpeername()

    def on_peer_close(self, event):
        print "on_peer_close: %s" % self._getpeername()

    def on_close(self):
        print "close connection to %s" % self._getpeername()

    def on_connected(self):
        print "worker: %s accepted new connection from %s" % \
            (os.getpid(), self._getpeername())

    def before_read_data(self):
        print "before_read_data: %s" % self._getpeername()

    def after_read_data(self):
        print "after_read_data : %s" % self._getpeername()

    def before_write_data(self):
        print "before_write_data: %s" % self._getpeername()

    def after_write_data(self):
        print "after_write_data: %s" % self._getpeername()

    def read_data_ok(self):
        print "read_data_ok: %s" % self._getpeername()

    def write_data_ok(self):
        print "write_data_ok: %s" % self._getpeername()

