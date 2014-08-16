import os, pprint, select, socket, ssl, sys
from OpenSSL import SSL

path = '/home/pi/ssl/client/'
port = 9901

def verify_cb(conn, cert, errnum, depth, ok):
    # This obviously has to be updated
    print 'Got certificate: %s' % cert.get_subject()
    return ok

dir = path
if dir == '':
    dir = os.curdir

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# Require to get a certificate from the server
ssl_sock = ssl.wrap_socket(s,
                keyfile=os.path.join(dir, 'newkey_nopass.pem'),
                certfile=os.path.join(dir, 'newcert.pem'),
                ca_certs=os.path.join(dir, 'cacert.pem'),
                ssl_version=ssl.PROTOCOL_TLSv1,
                cert_reqs=ssl.CERT_REQUIRED)

ssl_sock.connect(('localhost', port))
print 'Connected...'

print repr(ssl_sock.getpeername())
print ssl_sock.cipher()
print pprint.pformat(ssl_sock.getpeercert())

while 1:
    try:
        ssl_sock.sendall('GET / HTTP/1.1\r\n\r\n')
        response = ssl_sock.recv(1024)
        print len(response)
    except SSL.Error:
        print 'The Connection was closed unexpectedly.'
        break


ssl_sock.shutdown()
ssl_sock.close()
