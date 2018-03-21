import os
import posixpath
import ssl
import threading
import time

import pyftpdlib.authorizers
import pyftpdlib.handlers
import pyftpdlib.servers
import six

from six.moves import BaseHTTPServer
from six.moves import urllib


class FTPServer(object):

    def __init__(self, port, root, report_size):
        class FTPHandlerNoSIZE(pyftpdlib.handlers.FTPHandler):
            proto_cmds = {k: v for k, v in six.iteritems(pyftpdlib.handlers.proto_cmds) if k != 'SIZE'}

        authorizer = pyftpdlib.authorizers.DummyAuthorizer()
        authorizer.add_anonymous(root)
        handler = pyftpdlib.handlers.FTPHandler if report_size else FTPHandlerNoSIZE
        handler.authorizer = authorizer
        self.server = pyftpdlib.servers.FTPServer(('', port), handler)

    def serve(self):
        self.server.serve_forever()


class HTTPServer(object):

    def __init__(self, port, cert, root, report_size):
        class RequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):

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

        self.server = BaseHTTPServer.HTTPServer(('', port), RequestHandler)
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
