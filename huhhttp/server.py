import io
import re
import urllib.parse

from huhhttp.header import Request
import asyncio
import logging

_logger = logging.getLogger(__name__)


class ProtocolError(ValueError):
    pass


class CloseConnection(ValueError):
    pass


class Server(object):
    def __init__(self, handlers=None):
        self.handlers = handlers or []

    def __call__(self, reader, writer):
        while True:
            try:
                request = yield from self._process_request(reader, writer)
                yield from self._dispatch(reader, writer, request)
            except ProtocolError as error:
                _logger.info('Client error %s', error)
                writer.write(b'HTTP/1.1 400 ')
                writer.write(error.args[0].encode('ascii'))
                writer.write(b'\r\n\r\n')
                writer.write(error.args[0].encode('ascii'))
                writer.close()
                return
            except CloseConnection:
                writer.close()
                return
            except ConnectionError:
                writer.close()
                return
            except Exception:
                _logger.exception('Server error.')
                writer.close()
                return

    @asyncio.coroutine
    def _process_request(self, reader, writer):
        lines = []
        bytes_read = 0

        while True:
            line = yield from reader.readline()
            _logger.debug('Got line %s', line)

            if line[-1:] != b'\n':
                raise CloseConnection()

            if not line.strip():
                break

            lines.append(line)

            bytes_read += len(line)

            if bytes_read > 4096:
                raise ProtocolError('Header too long')

        if not lines:
            raise ProtocolError('No header.')

        _logger.debug('Parse request.')

        request = Request()
        request.parse_lines(lines)

        if b'content-length' in request.fields:
            try:
                length = int(request.fields[b'content-length'])
            except ValueError:
                raise ProtocolError('Bad content length')
            if length < 0:
                raise ProtocolError('Negative content length')
            elif length > 10000:
                raise ProtocolError('Content length too big')

            _logger.debug('Reading payload len=%s', length)
            bytes_left = length
            request.payload = io.BytesIO()

            while bytes_left > 0:
                data = yield from reader.read(min(bytes_left, 4096))

                request.payload.write(data)
                bytes_left -= len(data)

            request.payload.seek(0)

        return request

    @asyncio.coroutine
    def _dispatch(self, reader, writer, request):
        parse_result = urllib.parse.urlsplit(request.uri)

        path = parse_result.path

        if path[0:1] != b'/':
            raise ProtocolError('Bad path')

        for pattern, handler_class in self.handlers:
            match = re.fullmatch(pattern, path)
            if match:
                handler = handler_class(self, reader, writer, request, match)
                return (yield from handler())
        else:
            _logger.debug('Handler not found for path %s', path)
            writer.write(b'HTTP/1.1 404 Not found\r\n')
            writer.write(b'Content-Length: 3\r\n')
            writer.write(b'\r\n')
            writer.write(b'404')
