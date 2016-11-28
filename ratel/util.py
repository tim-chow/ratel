import socket
import types

def get_server_socket(ip, port, backlog):
    sock = socket.socket(socket.AF_INET,
        socket.SOCK_STREAM)
    sock.setsockopt(socket.IPPROTO_TCP,
        socket.TCP_NODELAY, 1)
    sock.setblocking(False)
    try:
        sock.bind((ip, port))
        sock.listen(backlog)
    except:
        sock.close()
        raise

    return sock


class SafeModeException(StandardError):
    def __init__(self, oriex, *a, **kw):
        StandardError.__init__(self, *a, **kw)
        self._oriex = oriex

    def get_exception(self):
        return self._oriex

    def __str__(self):
        return str(self._oriex)

class SafeModeMetaClass(type):
    def __new__(mcs, name, bases, attrs):
        for attr_name, attr_value in attrs.iteritems():
            if isinstance(attr_value, types.FunctionType):
                attrs[attr_name] = SafeModeMetaClass. \
                    ignore_exceptions(attr_value)
        return type.__new__(mcs, name, bases, attrs)

    @staticmethod
    def ignore_exceptions(f):
        def _inner(*a, **kw):
            try:
                return f(*a, **kw)
            except Exception as ex:
                return SafeModeException(ex)
        return _inner

