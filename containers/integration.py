import cgi
import hashlib
import http.server
import io
import os
import posixpath
import ssl
import threading
import time
import urllib.parse

import pyftpdlib.authorizers
import pyftpdlib.handlers
import pyftpdlib.servers


class FTPServer:

    def __init__(self, port, root, report_size):
        class FTPHandlerNoSIZE(pyftpdlib.handlers.FTPHandler):
            proto_cmds = {k: v for k, v in pyftpdlib.handlers.proto_cmds.items() if k != 'SIZE'}

        authorizer = pyftpdlib.authorizers.DummyAuthorizer()
        authorizer.add_anonymous(root)
        handler = pyftpdlib.handlers.FTPHandler if report_size else FTPHandlerNoSIZE
        handler.authorizer = authorizer
        self.server = pyftpdlib.servers.FTPServer(('', port), handler)

    def serve(self):
        self.server.serve_forever()


class HTTPServer:

    def __init__(self, port, cert, root, report_size):
        class RequestHandler(http.server.BaseHTTPRequestHandler):

            def do_GET(self):
                path = self.path.split('?', 1)[0].split('#', 1)[0]
                path = urllib.parse.unquote(path)
                path = posixpath.normpath(path)
                path = os.path.join(root, path.lstrip('/'))
                try:
                    with open(path, 'rb') as f:
                        data = f.read()
                    self.send_response(200)
                    content_type = 'application/json' if 'versioneers' in path else 'application/octet-stream'
                    self.send_header('Content-Type', content_type)
                    self.send_header('Content-Transfer-Encoding', 'binary')
                    if report_size:
                        self.send_header('Content-Length', len(data))
                    self.end_headers()
                    self.wfile.write(data)
                except FileNotFoundError:
                    self.send_error(404)

            def do_POST(self):
                def dechunk(f):
                    bio = io.BytesIO()
                    while True:
                        chunksize = bytearray()
                        while not chunksize.endswith(b'\r\n'):
                            chunksize += f.read(1)
                        chunksize = chunksize.decode().split(':')[0]
                        chunksize = int(chunksize, 16)
                        if chunksize == 0:
                            break
                        chunk = f.read(chunksize)
                        assert(f.read(2) == b'\r\n')
                        bio.write(chunk)
                    bio.seek(0)
                    return bio

                def verify_hash(f, hashtype, hsh):
                    try:
                        chksum = hashlib.new(hashtype)
                    except ValueError:
                        return False
                    chksum.update(f.read())
                    return chksum.hexdigest() == hsh

                if self.headers.get('Transfer-Encoding') == 'chunked':
                    fp = dechunk(self.rfile)
                else:
                    fp = self.rfile
                data = cgi.FieldStorage(fp=fp, headers=self.headers,
                                        environ={'REQUEST_METHOD': 'POST'},
                                        # accept maximum of 10MB of data
                                        limit=10 * 1024 * 1024)
                try:
                    if 'filename' in data:
                        resp = b'Missing'
                        self.send_response(200)
                        self.send_header('Content-Type', 'text/plain')
                        self.send_header('Content-Length', len(resp))
                        self.end_headers()
                        self.wfile.write(resp)
                    else:
                        hashtype = [k for k in data.keys() if k.endswith('sum')][0]
                        hsh = data[hashtype].value
                        hashtype = hashtype.split('sum')[0]
                        if verify_hash(data['file'].file, hashtype, hsh):
                            self.send_response(204)
                            self.end_headers()
                        else:
                            self.send_error(500)
                except (KeyError, IndexError):
                    self.send_error(400)

        self.server = http.server.HTTPServer(('', port), RequestHandler)
        if cert:
            self.server.socket = ssl.wrap_socket(self.server.socket, certfile=cert, server_side=True)

    def serve(self):
        self.server.serve_forever()


def main():
    servers = [
        FTPServer(2100, '/srv', True),
        FTPServer(2101, '/srv', False),
        HTTPServer(8000, None, '/srv', True),
        HTTPServer(8001, None, '/srv', False),
        HTTPServer(4430, '/cert.pem', '/srv', True),
        HTTPServer(4431, '/cert.pem', '/srv', False),
    ]
    threads = [threading.Thread(target=s.serve) for s in servers[1:]]
    for t in threads:
        t.setDaemon(True)
        t.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
