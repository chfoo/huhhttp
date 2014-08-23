import gzip
import io
import zlib


class GzipCompressor(object):
    def __init__(self):
        self._buffer = io.BytesIO()
        self._gzip_file = gzip.GzipFile(
            mode='wb', compresslevel=6, fileobj=self._buffer)

    def write(self, data):
        self._gzip_file.write(data)
        new_data = self._buffer.getvalue()
        self._buffer.seek(0)
        self._buffer.truncate()
        return new_data

    def close(self):
        self._gzip_file.close()
        new_data = self._buffer.getvalue()
        self._buffer.close()
        return new_data


class DeflateCompressor(object):
    def __init__(self):
        self._compress_obj = zlib.compressobj(6)

    def write(self, data):
        return self._compress_obj.compress(data)

    def close(self):
        return self._compress_obj.flush()


class RawDeflateCompressor(object):
    def __init__(self):
        self._compress_obj = zlib.compressobj(6)
        self._header_written = False

    def write(self, data):
        if self._header_written:
            return self._compress_obj.compress(data)
        else:
            self._header_written = True
            return self._compress_obj.compress(data)[2:]

    def close(self):
        return self._compress_obj.flush()[:-4]
