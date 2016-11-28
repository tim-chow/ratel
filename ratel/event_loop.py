import sys
import select

if not sys.platform.lower().startswith("linux2"):
    print >>sys.stderr, "\033[31mCurrently, only support epoll\033[0m"
    sys.exit(1)

class SocketEvent:
    if not "EPOLLRDHUP" in dir(select):
        select.EPOLLRDHUP = 0x2000

    ERROR = select.EPOLLHUP | select.EPOLLERR
    CLOSE = select.EPOLLRDHUP | ERROR
    READ = select.EPOLLIN | CLOSE
    WRITE = select.EPOLLOUT | CLOSE

    # Custom mask
    STOP = 0x20000000


class EventLoop:
    def __init__(self, server_socket):
        self._server_socket = server_socket
        self._fd_to_socket = {server_socket.fileno(): server_socket}
        self._fd_to_command = {}

        self._event_loop = select.epoll()
        self._event_loop.register(server_socket.fileno(), SocketEvent.READ)

        self._timeout = 0.001
        self._still_running = True
        self._is_running = False

    def register_command_class(self, command_class):
        self._command_class = command_class
        return self

    def stop(self):
        self._still_running = False

    def start(self, *a, **kw):
        if self._is_running:
            raise RuntimeError("EventLoop has already started")
        if not hasattr(self, "_command_class"):
            raise RuntimeError("No command class found")
        self._is_running = True
        while self._still_running:
            self._before_poll()
            try:
                self._poll(*a, **kw)
            except IOError as ex:
                if ex.errno == 4:
                    print str(ex)
            self._after_poll()
        self._close()

    def _before_poll(self):
        for fd, command in self._fd_to_command.iteritems():
            command.before_poll()

    def _after_poll(self):
        for fd, command in self._fd_to_command.iteritems():
            command.after_poll()

    def _close(self):
        for fd, command in self._fd_to_command.iteritems():
            command.on_shutdown()
        for fd, sock in self._fd_to_socket.iteritems():
            sock.close()

        self._is_running = False
        self._event_loop.close()

    def _poll(self, timeout=None):
        events = self._event_loop.poll(timeout or self._timeout)
        if not events:
            return
        for fd, event in events:
            sock = self._fd_to_socket[fd]
            command = self._fd_to_command.get(fd)

            if event & SocketEvent.CLOSE:
                command.on_peer_close(event)
                sock.close()
                self._fd_to_socket.pop(fd)
                self._fd_to_command.pop(fd)
                continue

            if event & SocketEvent.READ and sock == self._server_socket:
                new_connection, addr = sock.accept()
                new_connection.setblocking(False)
                fd = new_connection.fileno()
                self._fd_to_socket[fd] = new_connection
                command = self._command_class(new_connection, SocketEvent)
                self._fd_to_command[fd] = command
                command.on_connected()
                self._on_next_event(new_connection, fd, command, "register")
                continue

            if event & SocketEvent.READ:
                try:
                    command.before_read_data()
                    command.on_data_in.next()
                    command.after_read_data()
                except StopIteration:
                    command.read_data_ok()
                    self._on_next_event(sock, fd, command, "modify")
                continue

            if event & SocketEvent.WRITE:
                try:
                    command.before_write_data()
                    command.on_data_out.next()
                    command.after_write_data()
                except StopIteration:
                    command.write_data_ok()
                    self._on_next_event(sock, fd, command, "modify")
                continue

    def _on_next_event(self, sock, fd, command, modify_or_register):
        next_event = command.get_event()
        if not (next_event & SocketEvent.STOP):
            getattr(self._event_loop, modify_or_register)(fd, next_event)
            return

        command.on_close()
        sock.close()
        self._fd_to_socket.pop(fd)
        self._fd_to_command.pop(fd)

