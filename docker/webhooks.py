import hashlib
import hmac
import http.server
import json
import os
import sys
import tempfile
import threading

import distutils.core
import git
import twine.commands.upload


class PyPI:

    @staticmethod
    def release(url, tag):
        with tempfile.TemporaryDirectory() as wd:
            os.chdir(wd)
            repo = git.Repo.clone_from(url, wd)
            repo.git.checkout(tag)
            sys.path.insert(0, wd)
            distutils.core.run_setup(os.path.join(wd, 'setup.py'),
                                     ['sdist', 'bdist_wheel', '--universal'])
            twine.commands.upload.main([os.path.join(wd, 'dist', '*')])


class Worker(threading.Thread):

    def __init__(self):
        super(Worker, self).__init__(daemon=True)
        self.condition = threading.Condition()
        self.url = None
        self.tag = None

    def run(self):
        while True:
            with self.condition:
                self.condition.wait()
                PyPI.release(self.url, self.tag)


class HTTPServer:

    def __init__(self, port):
        class RequestHandler(http.server.BaseHTTPRequestHandler):

            def do_POST(self):
                def verify(signature, data):
                    try:
                        sha, signature = signature.split('=')
                    except ValueError:
                        return False
                    if sha != 'sha1':
                        return False
                    mac = hmac.new(os.environb.get(b'SECRET', bytes()), data, hashlib.sha1)
                    return hmac.compare_digest(mac.hexdigest(), signature)

                length = int(self.headers.get('Content-Length', 0))
                data = self.rfile.read(length)
                if not verify(self.headers.get('X-Hub-Signature'), data):
                    self.send_error(403)
                    return
                event = self.headers.get('X-GitHub-Event')
                if event == 'ping':
                    self.send_response(204)
                    self.end_headers()
                    return
                if event == 'release':
                    data = json.loads(data)
                    if self.server.worker.condition.acquire(blocking=False):
                        try:
                            self.server.worker.url = data.get('repository', {}).get('clone_url')
                            self.server.worker.tag = data.get('release', {}).get('tag_name')
                            self.server.worker.condition.notify()
                        finally:
                            self.server.worker.condition.release()
                self.send_response(204)
                self.end_headers()

        self.server = http.server.HTTPServer(('', port), RequestHandler)
        self.server.worker = Worker()

    def serve(self):
        self.server.worker.start()
        self.server.serve_forever()


def main():
    try:
        HTTPServer(80).serve()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
