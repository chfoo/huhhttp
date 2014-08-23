import re
import collections.abc


class Fields(collections.abc.MutableMapping):
    def __init__(self):
        self.doc = {}

    @classmethod
    def normalize_key(cls, key):
        return key.title()

    def __getitem__(self, key):
        assert isinstance(key, bytes)
        return self.doc[self.normalize_key(key)]

    def __setitem__(self, key, value):
        assert isinstance(key, bytes)
        assert isinstance(value, bytes)
        self.doc[self.normalize_key(key)] = value

    def __delitem__(self, key):
        assert isinstance(key, bytes)
        del self.doc[self.normalize_key(key)]

    def __iter__(self):
        return iter(self.doc)

    def __len__(self):
        return len(self.doc)

    def parse(self, data):
        self.parse_lines(data.split(b'\n'))

    def parse_lines(self, lines):
        unfolded_lines = []
        for line in lines:
            if line[0:1] in (b' ', b'\t'):
                if not unfolded_lines:
                    continue

                line = line.strip()
                unfolded_lines[-1] = unfolded_lines[-1] + b' ' + line
            else:
                unfolded_lines.append(line)

        for line in unfolded_lines:
            key, value = line.split(b':', 1)
            key = key.strip()
            value = value.strip()

            self[key] = value

    def to_bytes(self):
        return b'\r\n'.join(
            key + b':' + value for key, value in self.items()) + b'\r\n'


class Request(object):
    def __init__(self, method=None, uri=None, version=None):
        self.method = method
        self.uri = uri
        self.version = version
        self.fields = Fields()
        self.payload = None

    def parse_lines(self, lines):
        match = re.match(
            br'(\w+)\s+(\S+)\s+(HTTP/\d+\.\d+)', lines[0], re.IGNORECASE)

        if not match:
            raise ValueError('Failed to parse status line.')

        self.method = match.group(1)
        self.uri = match.group(2)
        self.version = match.group(3)

        self.fields.parse_lines(lines[1:])

    def to_bytes(self):
        return b''.join([
            self.method, b' ', self.uri, b' ', self.version, b'\r\n',
            self.fields.to_bytes()
        ])


class Response(object):
    def __init__(self, version=None, status_code=None, reason=None):
        self.version = version
        self.status_code = status_code
        self.reason = reason
        self.fields = Fields()
        self.payload = None

    def parse_lines(self, lines):
        match = re.match(
            br'(HTTP/\d+\.\d+)\s+(\d+)\s+([^\r\n]*)', lines[0], re.IGNORECASE)

        if not match:
            raise ValueError('Failed to parse status line.')

        self.version = match.group(1)
        self.status_code = int(match.group(2))
        self.reason = match.group(3)

        self.fields.parse_lines(lines[1:])

    def to_bytes(self):
        return b''.join([
            self.version, b' ',
            str(self.status_code).encode('ascii'), b' ', self.reason, b'\r\n',
            self.fields.to_bytes()
        ])
