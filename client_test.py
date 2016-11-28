import time
import struct
import socket

def read(sock, n):
    tmp = ""
    while True:
        tmp = tmp + sock.recv(n)
        if len(tmp) < n:
            continue
        break
    return tmp

for i in range(200):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("127.0.0.1", 8899))
    data = "1234567890" * 100000
    data = struct.pack("!I", len(data)) + data
    sock.send(data)

    length = struct.unpack("!I", sock.recv(4))[0]
    print "length =", length

    data = read(sock, length)
    print "len(data) =", len(data)
    sock.close()

