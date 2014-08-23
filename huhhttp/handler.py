import asyncio
import hashlib
import io
import socket
import struct

from huhhttp.header import Response


class StopProcessing(Exception):
    pass


class Handler(object):
    def __init__(self, server, reader, writer, request, match):
        self.server = server
        self.reader = reader
        self.writer = writer
        self.request = request
        self.match = match
        self.response = None
        self.closed = False
        self.streaming = False
        self.buffer = None
        self.buffer_hash = None
        self.allowed_methods = (b'GET', b'HEAD')

    def __call__(self):
        try:
            yield from self.prepare()
            yield from self.process()
            yield from self.finish()
        except StopProcessing:
            pass

    @asyncio.coroutine
    def prepare(self):
        if self.request.method not in self.allowed_methods:
            yield from self.write_header(405, b'Method not allow')
            yield from self.finish()
            raise StopProcessing()

    @asyncio.coroutine
    def process(self):
        raise NotImplementedError()

    @asyncio.coroutine
    def finish(self):
        if self.streaming:
            yield from self.write(b'0\r\n\r\n')
        elif self.response:
            if b'Content-Length' not in self.response.fields:
                self.response.fields[b'Content-Length'] = str(
                    self.buffer.tell()).encode('ascii')

            if b'Etag' not in self.response.fields and self.buffer_hash:
                self.response.fields[b'Etag'] = self.buffer_hash.hexdigest(
                    ).encode('ascii')

            if self.response.status_code == 200 and \
                    b'If-None-Match' in self.request.fields and \
                    self.request.fields.get(b'If-None-Match') == \
                    self.response.fields.get(b'Etag'):
                self.response.status_code = 304
                yield from self.write(self.response.to_bytes())
                yield from self.write(b'\r\n')
            else:
                yield from self.write(self.response.to_bytes())
                yield from self.write(b'\r\n')

                if self.request.method != b'HEAD':
                    yield from self.write(self.buffer.getvalue())

        if not self.closed and (
                self.request.fields.get(b'connection') == b'close' or
                self.request.version != b'HTTP/1.1'):
            self.close()

    def close(self):
        self.closed = True
        self.writer.close()

    @asyncio.coroutine
    def write(self, data):
        self.writer.write(data)
        yield from self.writer.drain()

    @asyncio.coroutine
    def write_header(self, status_code, reason=b'', headers=None):
        self.response = Response(
            version=b'HTTP/1.1', status_code=status_code, reason=reason)

        if headers is not None:
            self.response.fields.update(headers)

        yield from self.begin_content()

    @asyncio.coroutine
    def begin_content(self):
        if self.streaming:
            if b'Transfer-encoding' not in self.response.fields:
                self.response.fields[b'Transfer-Encoding'] = b'chunked'

            yield from self.write(self.response.to_bytes())
            yield from self.write(b'\r\n')
        else:
            self.buffer = io.BytesIO()
            self.buffer_hash = hashlib.sha1()

    @asyncio.coroutine
    def write_content(self, data):
        if self.streaming:
            yield from self.write_chunk(data)
        else:
            self.buffer.write(data)
            self.buffer_hash.update(data)
            if self.buffer.tell() > 10000:
                self.stream()
                yield from self.begin_content()
                yield from self.write_chunk(self.buffer.getvalue())

    @asyncio.coroutine
    def write_chunk(self, data):
        yield from self.write('{:x}'.format(len(data)).encode('ascii'))
        yield from self.write(b'\r\n')
        yield from self.write(data)
        yield from self.write(b'\r\n')

    def stream(self):
        self.streaming = True

    def reset_connection(self):
        # http://stackoverflow.com/a/6440364/1524507
        sock = self.writer.get_extra_info('socket')
        l_onoff = 1
        l_linger = 0
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER,
                        struct.pack('ii', l_onoff, l_linger))
        sock.close()
        self.close()
