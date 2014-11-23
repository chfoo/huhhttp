import asyncio
import calendar
import collections
import email.utils
import gzip
import html
import logging
import os.path
import re
import socket
import struct
import time
import urllib.parse

from huhhttp.compress import GzipCompressor, DeflateCompressor, \
    RawDeflateCompressor
from huhhttp.fuzz import ConnectionAction, CompressType
from huhhttp.handler import Handler, StopProcessing
from huhhttp.post import POSTS, POST_KEYS
from huhhttp.server import Server
from huhhttp.template import SITE_TEMPLATE, BANNER_NAV, INDEX_CONTENT, \
    SIMPLE_404, CALENDAR_TEMPLATE, WEB_RING_REDIRECT, WEB_RING_CONTENT, \
    GUESTBOOK_INTRO, GUESTBOOK_BODY, GUESTBOOK_ENTRY, POST_ENTRY, RSS_TEMPLATE, \
    ATOM_TEMPLATE, CSI, DEFAULT_REASON, OSC


_logger = logging.getLogger(__name__)


class FuzzReaderWrapper(object):
    def __init__(self, reader, writer, fuzzer):
        self._reader = reader
        self._writer = writer
        self._fuzzer = fuzzer
        self._fuzz = None
        self._ready_to_fuzz = False

    def __getattr__(self, key):
        return getattr(self._reader, key)

    @property
    def fuzz_session(self):
        return self._fuzz

    @asyncio.coroutine
    def read(self, length=-1):
        if not (yield from self._fuzz_read()):
            return (yield from self._reader.read(length))
        else:
            return b''

    @asyncio.coroutine
    def readline(self):
        if not (yield from self._fuzz_read()):
            return (yield from self._reader.readline())
        else:
            return b''

    @asyncio.coroutine
    def _fuzz_read(self):
        if not self._fuzz and self._ready_to_fuzz:
            self._new_fuzz_session()
        elif not self._fuzz:
            self._ready_to_fuzz = True
            return

        hang_time = self._fuzz.hang_time()
        connection_action = self._fuzz.connection_action()

        if hang_time:
            yield from asyncio.sleep(hang_time)

        if connection_action == ConnectionAction.close:
            self.close()
            return True
        elif connection_action == ConnectionAction.reset:
            self.reset_connection()
            return True

    def close(self):
        self._writer.close()

    def reset_connection(self):
        # http://stackoverflow.com/a/6440364/1524507
        sock = self._writer.get_extra_info('socket')
        l_onoff = 1
        l_linger = 0
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER,
                        struct.pack('ii', l_onoff, l_linger))
        sock.close()
        self._writer.close()

    def _new_fuzz_session(self):
        assert not self._fuzz
        fuzz_session = self._fuzzer.session()
        _logger.info('Fuzz session: counter=%d threshold=%.04f',
                     self._fuzzer.counter, fuzz_session.threshold)
        self._fuzz = fuzz_session


class SiteServer(Server):
    def __init__(self, fuzzer, restart_interval=10000):
        super().__init__(HANDLERS)
        self.fuzzer = fuzzer
        self.restart_interval = restart_interval
        self.asyncio_server = None

    @asyncio.coroutine
    def _process_request(self, reader, writer):
        wrapper = FuzzReaderWrapper(reader, writer, self.fuzzer)
        request = yield from super()._process_request(wrapper, writer)

        request.fuzz_session = wrapper.fuzz_session
        return request


class FuzzHandler(Handler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.server.fuzzer.counter and \
                self.server.fuzzer.counter % self.server.restart_interval == 0:
            if self.server.asyncio_server:
                _logger.info('Server close')
                self.server.fuzzer.counter += 1
                self.server.asyncio_server.close()
                asyncio.get_event_loop().stop()
                raise StopProcessing()

        _logger.info('Request: %s %s',
                     '{0[0]}:{0[1]}'.format(
                         self.writer.get_extra_info('socket').getpeername()),
                     self.match.string
                     )

        self._fuzz = self.request.fuzz_session

        accept_encoding = self.request.fields.get(b'Accept-Encoding', b'')
        self._compress_type = self._fuzz.compress_type(
            requested=accept_encoding.decode('ascii', 'replace'))

        if self._compress_type in (CompressType.gzip,
                                   CompressType.gzip_broken):
            self._compressor = GzipCompressor()
        elif self._compress_type == CompressType.deflate:
            self._compressor = DeflateCompressor()
        elif self._compress_type == CompressType.raw_default:
            self._compressor = RawDeflateCompressor()
        else:
            self._compressor = None

    @asyncio.coroutine
    def begin_content(self):
        if self._compress_type and self.response and \
                b'Content-Encoding' not in self.response.fields:
            if self._compress_type in (CompressType.gzip,
                                       CompressType.not_gzip,
                                       CompressType.gzip_broken):
                self.response.fields[b'Content-Encoding'] = b'gzip'
            elif self._compress_type in (CompressType.deflate,
                                         CompressType.raw_default):
                self.response.fields[b'Content-Encoding'] = b'deflate'

        yield from super().begin_content()

    @asyncio.coroutine
    def write_content(self, data):
        if self._compressor:
            new_data = self._compressor.write(data)
            if new_data:
                yield from super().write_content(new_data)
        else:
            yield from super().write_content(data)

    @asyncio.coroutine
    def finish(self):
        if self._compressor:
            if self._compress_type == CompressType.gzip_broken:
                data = self._compressor.close()[:-4] + b'\xde\xad\xbe\xef'
                yield from super().write_content(data)
            else:
                yield from super().write_content(self._compressor.close())

        yield from super().finish()

    @asyncio.coroutine
    def write(self, data):
        hang_time = self._fuzz.hang_time()
        connection_action = self._fuzz.connection_action()

        if hang_time:
            yield from asyncio.sleep(hang_time)

        if connection_action == ConnectionAction.close:
            self.close()
            return
        elif connection_action == ConnectionAction.reset:
            self.reset_connection()
            return

        data = self._fuzz.mangle(data)

        yield from super().write(data)


class SiteHandler(FuzzHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.encoding = 'utf_8'
        self.charset = ''

    def fuzz_encoding(self):
        codec_name, encoding_name = self._fuzz.codec()
        self.encoding = codec_name
        self.charset = self._fuzz.charset()
        if self.charset:
            self.charset = self.charset.format(name=encoding_name)

    @asyncio.coroutine
    def process(self):
        self.fuzz_encoding()
        yield from self.write_cms()

    @asyncio.coroutine
    def write_cms(self, status_code=200, reason=DEFAULT_REASON):
        self.stream()
        yield from self.write_header(
            status_code, reason,
            headers={
                b'Content-Type': b'text/html',
                b'X-Dragon': OSC + b'2;Smaug was here!\x07'
            })
        yield from self.write_content(self.format_template())

    def format_template(self):
        return SITE_TEMPLATE.format(
            doctype=self._fuzz.doctype(),
            charset=self.charset,
            banner=BANNER_NAV,
            title=self.get_title(),
            body=self.get_body(),
            recent_posts=self.recent_posts(),
        ).encode(self.encoding, 'replace')

    def get_title(self):
        return ('A WEB SITE FOR SMAUG THE DRAGON FOR WHO WITHIN '
                'WE PLACE OUR SOUL, TREASURES, AND OUR DEEPEST FEARS'
                )

    def get_body(self):
        return ''

    def recent_posts(self):
        text = []

        for date in POST_KEYS[:3]:
            post = POSTS[date]
            text.append(
                '<LI><A HREF="wirdpress/post/{}/{}/{}/{}">{}</A>'
                .format(date[0], date[1], date[2],
                        post_content_to_url_slug(post),
                        post[:60])
            )

        return ''.join(text)

    def all_posts(self):
        text = []

        for date in POST_KEYS:
            post = POSTS[date]
            text.append(
                '<LI><A HREF="wirdpress/post/{}/{}/{}/{}">{}</A>'
                .format(date[0], date[1], date[2],
                        post_content_to_url_slug(post),
                        post[:60])
            )

        return ''.join(text)


class SmokeTestHandler(SiteHandler):
    @asyncio.coroutine
    def process(self):
        yield from self.write_header(200, b'OK')
        yield from self.write_content(b'It looks ok!')


class HomeHandler(SiteHandler):
    def get_body(self):
        return INDEX_CONTENT + DEFAULT_REASON.decode('ascii')


class ImagesHandler(SiteHandler):
    ASSET_DIR = os.path.join(os.path.dirname(__file__), 'asset')
    EXTENSION_MAP = {
        '.bmp': 'image/bmp',
        '.css': 'text/css',
        '.js': 'application/javascript',
        '.ogg': 'application/ogg',
        '.xml': 'application/xml',
    }

    @asyncio.coroutine
    def process(self):
        filename = self.match.group(1)
        filename = filename.replace(b'..', b'_')
        filename = filename.decode('ascii', 'replace')

        if 'songofsmaug' in filename:
            filename = 'songofsmaug.ogg'

        path = os.path.join(self.ASSET_DIR, filename)
        if not path.startswith(self.ASSET_DIR):
            raise Exception('Paths not matching')

        extension = os.path.splitext(path)[1]

        content_type = self.EXTENSION_MAP.get(
            extension, 'text/html').encode('ascii')

        if os.path.isfile(path):
            before_date_tuple = email.utils.parsedate(
                self.request.fields.get(b'If-Modified-Since', b'')
                .decode('ascii', 'replace'))

            if before_date_tuple:
                before_time = time.mktime(before_date_tuple)
            else:
                before_time = None

            if before_time is not None and \
                    before_time >= int(os.path.getmtime(path)):
                yield from self.write_header(
                    304,
                    b'One does not simply HTTP into Mordor',
                    headers={
                        b'Last-modified': email.utils.formatdate(
                            os.path.getmtime(path)).encode('ascii'),
                    })
                yield from self.write_content(b'What is HTTP?')
                return

            yield from self.write_header(
                200, b'',
                headers={
                    b'Content-Type': content_type,
                    b'Last-modified': email.utils.formatdate(
                        os.path.getmtime(path)).encode('ascii'),
                    b'Accept-Ranges': b'bytes',
                    b'Content-Range': b'bytes 0-',
                    b'Expires': b'Thu, Apr 01 Sep 1993 24:00:00 GMT',
                })

            with open(path, 'rb') as file:
                while True:
                    data = file.read(4096)

                    if not data:
                        break

                    yield from self.write_content(data)
        else:
            yield from super().process()

    def get_body(self):
        return '<h1>404 Not Found</h2>'


class NotFoundHandler(SiteHandler):
    @asyncio.coroutine
    def process(self):
        yield from self.write_header(
            404, b'404 Not found', headers={b'Content-Type': b'text/html'})
        yield from self.write_content(SIMPLE_404.encode('utf16'))


class WebRingHandler(SiteHandler):
    def format_template(self):
        return WEB_RING_REDIRECT.encode('utf8') + super().format_template()


class WebRingPageHandler(SiteHandler):
    def fuzz_encoding(self):
        pass

    def get_body(self):
        return WEB_RING_CONTENT


class GuestbookIntroHandler(SiteHandler):
    def get_body(self):
        return GUESTBOOK_INTRO


class GuestbookHandler(SiteHandler):
    MESSAGES = collections.deque(maxlen=20)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.allowed_methods = (b'GET', b'POST')

    @asyncio.coroutine
    def process(self):
        if self.request.method == b'POST':
            message = self.request.payload.read(140)
            values = urllib.parse.parse_qs(
                message, strict_parsing=False,
                ).get(b'message')

            if values:
                self.MESSAGES.append(values[0].decode('ascii', 'replace'))

        yield from super().process()

    def get_body(self):
        recent = []

        for message in self.MESSAGES:
            recent.append(GUESTBOOK_ENTRY.format(entry=html.escape(message)))

        return GUESTBOOK_BODY.format(recent=''.join(recent))


class CalendarHandler(SiteHandler):
    MONTHS = ('Dummy',
              'Jan', 'Feb', 'Mar', 'May', 'Jun', 'July',
              'Aug', 'Nov', 'Sep', 'Oct', 'Nov', 'Dec')
    assert len(MONTHS) == 13

    @asyncio.coroutine
    def process(self):
        self.stream()
        self.year = int(self.match.group(1))
        self.month = int(self.match.group(2)) % 13
        self.day = int(self.match.group(3)) % 32
        yield from super().process()

    def get_title(self):
        return 'Posts on {} {} {}'.format(
            self.year, self.MONTHS[self.month], self.day)

    def get_body(self):
        prev_year = self.year
        prev_month = self.month - 1

        if prev_month <= 0:
            prev_year -= 1
            prev_month = 12

        prev_link = '/wirdpress/calendar/{}/{}/{}/'.format(
            prev_year, prev_month, 1)

        next_year = self.year
        next_month = self.month + 1

        if next_month >= 13:
            next_year += 1
            next_month = 1

        next_link = '/wirdpress/calendar/{}/{}/{}/'.format(
            next_year, next_month, 1)

        picker = []

        for row in calendar.monthcalendar(self.year, self.month):
            for day in row:
                if day:
                    picker.append(
                        '<A HREF=wirdpress/calendar/{}/{}/{}/>{}</A> '
                        .format(self.year, self.month, day, day)
                    )
                else:
                    picker.append('<A></A> ')

            picker.append('<BR>')

        picker = ''.join(picker)

        content = []
        content.append(
            CALENDAR_TEMPLATE.format(
                month=self.MONTHS[self.month],
                prev_link=prev_link, next_link=next_link, picker=picker)
        )

        post = POSTS.get((self.year, self.month, self.day))

        if post:
            slug = post_content_to_url_slug(post)
            content.append(
                '<A HREF="wirdpress/post/{}/{}/{}/{}">{}</A>'
                .format(self.year, self.month, self.day, slug, post[:60])
            )
        else:
            content.append('Sorry no posts on this day.')

        return ''.join(content)


class PostHandler(SiteHandler):
    @asyncio.coroutine
    def process(self):
        self.stream()
        self.year = int(self.match.group(1))
        self.month = int(self.match.group(2)) % 13
        self.day = int(self.match.group(3)) % 32

        self.post = POSTS.get((self.year, self.month, self.day))

        if self.post is not None:
            yield from super().process()
        else:
            yield from self.write_cms(404, b'Not found')

    def get_title(self):
        if self.post is not None:
            return self.post[:60]
        else:
            return 'Post not found'

    def get_body(self):
        if self.post is not None:
            key = (self.year, self.month, self.day)
            prev_post_key = self.get_prev_post_key(key)
            next_post_key = self.get_next_post_key(key)

            post_date = (
                '<A HREF=wirdpress/calendar/{}/{}/{}/>{} {} {}</A>'
                .format(self.year, self.month, self.day,
                        self.year, CalendarHandler.MONTHS[self.month],
                        self.day)
            )

            content = []

            if prev_post_key:
                year, month, day = prev_post_key
                post = POSTS[prev_post_key]
                slug = post_content_to_url_slug(post)
                content.append(
                    '<A HREF="wirdpress/post/{}/{}/{}/{}">PREV</A>'
                    .format(year, month, day, slug)
                )

            if next_post_key:
                year, month, day = next_post_key
                post = POSTS[next_post_key]
                slug = post_content_to_url_slug(post)
                content.append(
                    '<A HREF="wirdpress/post/{}/{}/{}/{}">NEXT</A>'
                    .format(year, month, day, slug)
                )

            return POST_ENTRY.format(
                date=post_date,
                entry=self.post,
                nav='\n'.join(content)
            )

        else:
            return (
                '<H1>Post not found</H1><P>'
                'Sorry, Smaug must have incinerated this post.'
            )

    @classmethod
    def get_prev_post_key(cls, date):
        try:
            index = POST_KEYS.index(date)
            return POST_KEYS[max(0, index - 1)]
        except ValueError:
            pass

    @classmethod
    def get_next_post_key(cls, date):
        try:
            index = POST_KEYS.index(date)
            return POST_KEYS[index + 1]
        except (ValueError, IndexError):
            pass


class AllPostsHandler(SiteHandler):
    def get_title(self):
        return 'All Smaug ghosts.'

    def get_body(self):
        return self.all_posts()


class DQueryMaxHandler(SiteHandler):
    @asyncio.coroutine
    def process(self):
        self.stream()
        yield from self.write_header(
            200, b'OK', headers={b'Content-type': b'application/javascript'})

        for i in range(100000):
            yield from self.write_content(
                b'/* DragonQuery maximum JS file*/\r\n')
            yield from self.write_content(b'var v')
            yield from self.write_content(str(i).encode('ascii'))
            yield from self.write_content(b'; /* pre-allocate some bytes */\n')

        yield from self.write_content(b'\xFF\xFE\x80')


class SmileyHandler(SiteHandler):
    @asyncio.coroutine
    def _messy_chunked(self):
        yield from self.write(b'HTTP/1.1 200\r\n')
        yield from self.write(b'Transfer-ENCODING: chunked\r\n\r\n')
        yield from self.write(b'5 ; horse\nhello\n0007\n world!\n0\n')
        yield from self.write(b'Animal: dolphin\r\nCake: delicious\r\n\r\n')

    @asyncio.coroutine
    def _overrun_response(self):
        yield from self.write(b'HTTP/1.1\t200\r\n')
        yield from self.write(b'Content-Length:\t100\r\n\r\n')
        yield from self.write(b'A' * 200)

    @asyncio.coroutine
    def _buffer_overflow(self):
        yield from self.write(b'HTTP/1.1 200\r\n')
        yield from self.write(b'Transfer-Encoding: chunked\r\n\r\n')

        for dummy in range(100):
            yield from self.write(b'0' * 10000)
        yield from self.write(b'1\r\n')
        yield from self.write(b'a\r\n')
        yield from self.write(b'0\r\n\r\n')

    @asyncio.coroutine
    def _content_length_and_chunked(self):
        yield from self.write(b'HTTP/1.1 200\r\n')
        yield from self.write(b'Transfer-Encoding: chunked\r\n')
        yield from self.write(b'Content-Length: 42\r\n\r\n')
        yield from self.write(b'5\r\nhello\r\n7\r\n world!\r\n0\r\n\r\n')

    @asyncio.coroutine
    def _utf8_header_and_short_close(self):
        yield from self.write(b'HTTP/1.0 200\r\n')
        yield from self.write(b'Emoji: ' + '🐲\r\n'.encode('utf8'))
        yield from self.write(b'Content-Length: 100\r\n\r\n')
        self.close()

    @asyncio.coroutine
    def _messy_header(self):
        yield from self.write(b'HTTP/1.1 200\r\n')
        yield from self.write('K: Кракозябры\r\n'.encode('koi8-r'))
        yield from self.write('M: 文字化け\r\n'.encode('shift_jis'))
        yield from self.write(b'Oops!\r\n')
        yield from self.write(b'Set-Cookie: \x00?#?+:%ff=hope you have '
                              b'cookies enabled!; expires=Dog\r\n' * 1000)
        yield from self.write(b'Content-Length: -12\r\n')
        yield from self.write(b'Set-Cookie: SMAUGYO')

    @asyncio.coroutine
    def _bad_content_length(self):
        yield from self.write(b'HTTP/1.0 200\r\n')
        yield from self.write(b'Content-Length: 3.14159\r\n')

    @asyncio.coroutine
    def _no_content(self):
        yield from self.write(b'HTTP/1.0 204\r\n\r\n')

    @asyncio.coroutine
    def _non_http_redirect(self):
        yield from self.write(b'HTTP/1.0 302\r\n')
        yield from self.write(b'Location: mailto:user@example.com\r\n')
        yield from self.write(b'Content-Length: 0\r\n\r\n')

    @asyncio.coroutine
    def _bad_http_redirect(self):
        yield from self.write(b'HTTP/1.0 302\r\n')
        yield from self.write(b'Location: I\'m going to Dragon City!\r\n')
        yield from self.write(b'Content-Length: 0\r\n\r\n')

    @asyncio.coroutine
    def _redirect_1(self):
        yield from self.write(b'HTTP/1.0 302\r\n')
        yield from self.write(b'Location: bounce2.gif\r\n')
        yield from self.write(b'Content-Length: 0\r\n\r\n')

    @asyncio.coroutine
    def _redirect_2(self):
        yield from self.write(b'HTTP/1.0 301\r\n')
        yield from self.write(b'Location: bounce1.gif\r\n')
        yield from self.write(b'Content-Length: 0\r\n\r\n')

    @asyncio.coroutine
    def _redirect_bad_url(self):
        yield from self.write(b'HTTP/1.0 301\r\n')
        yield from self.write(b'Location: http://]/\x00http://\r\n')
        yield from self.write(b'Content-Length: 0\r\n\r\n')

    @asyncio.coroutine
    def _big_header(self):
        yield from self.write(b'HTTP/1.0 200\r\n')
        for dummy in range(100):
            yield from self.write(b'A' * 10000)
        yield from self.write(b': A\r\n')
        yield from self.write(b'Content-Length: 0\r\n\r\n')

    @asyncio.coroutine
    def _zlib_bomb(self):
        yield from self.write(b'HTTP/1.1 200 Ha ha ha BWAAH HA HA HA!\r\n')
        yield from self.write(b'Content-Encoding: gzip\r\n')
        yield from self.write(b'Transfer-Encoding: chunked\r\n\r\n')

        path = os.path.join(ImagesHandler.ASSET_DIR, 'SMAUG.SMAUG.gz')
        with gzip.open(path, 'rb') as in_file:
            while True:
                data = in_file.read(64)

                if not data:
                    break

                yield from self.write(
                    '{:x}\r\n'.format(len(data)).encode('ascii'))
                yield from self.write(data)
                yield from self.write(b'\r\n')

        yield from self.write(b'0\r\n\r\n')

    @asyncio.coroutine
    def _empty_header(self):
        yield from self.write(b'\r\n\r\n')

    @asyncio.coroutine
    def _many_header(self):
        yield from self.write(b'HTTP/1.0 200 Headers\r\n')

        for num in range(10000):
            yield from self.write(
                ('H{0}: A header for me\r\n'
                 'H{0} : A header for you\r\n'
                 'H{0}  : I have a header\r\n'
                 'H{0}   : You have one too\r\n'
                 ).format(num).encode('ascii'))

        yield from self.write(b'\r\n')
        self.close()

    @asyncio.coroutine
    def process(self):
        func_map = {
            'happy3': self._messy_chunked,
            'frown1': self._overrun_response,
            'dancing4': self._buffer_overflow,
            'silly3': self._content_length_and_chunked,
            'oops': self._utf8_header_and_short_close,
            'stupid4': self._messy_header,
            'happy2': self._bad_content_length,
            'haha2': self._no_content,
            'smiles1': self._non_http_redirect,
            'happy1': self._bad_http_redirect,
            'bounce1': self._redirect_1,
            'bounce2': self._redirect_2,
            'cool4': self._redirect_bad_url,
            'jokes2': self._big_header,
            'surprise': self._zlib_bomb,
            'confused3': self._empty_header,
            'welcome4': self._many_header,
        }

        func = func_map.get(self.match.group(1).decode('ascii', 'replace'))

        if func:
            yield from func()
        else:
            yield from super().process()


class RssHandler(SiteHandler):
    @asyncio.coroutine
    def process(self):
        yield from self.write_header(
            200, headers={b'Content-Type': b'application/xml'})
        if self.match.group(1) == b'rss':
            yield from self.write_content(
                RSS_TEMPLATE.encode(self.encoding, 'replace'))
        else:
            yield from self.write_content(
                ATOM_TEMPLATE.encode(self.encoding, 'replace'))


class RobotsHandler(SiteHandler):
    @asyncio.coroutine
    def process(self):
        yield from self.write_header(200, b'Robotic Dragons Permitted')
        yield from self.write_content(b'# Please donate Bitcoins\n')
        yield from self.write_content(b'Sitemap: /images/sitemaps.xml\n')


def post_content_to_url_slug(text, encoding='utf-8'):
    text = re.sub(r'([\s<>"\']+)', '-', text[:60].strip().lower()).strip('-')
    return urllib.parse.quote(text, encoding=encoding)


HANDLERS = [
    (br'/smoketest', SmokeTestHandler),
    (br'/(index\.htm)?', HomeHandler),
    (br'/guestbook\.htm', GuestbookIntroHandler),
    (br'/cgi-bin/guestbook\.cgi', GuestbookHandler),
    (br'/web_ring\.htm', WebRingHandler),
    (br'/images/dquery-max\.js', DQueryMaxHandler),
    (br'/images/(.*)', ImagesHandler),
    (br'/wirdpress/post/(\d{4})/(\d{1,2})/(\d{1,2})/(.*)', PostHandler),
    (br'/wirdpress/post/all/posts', AllPostsHandler),
    (br'/wirdpress/page/web_ring', WebRingPageHandler),
    (br'/wirdpress/calendar/(\d{4})/(\d{1,2})/(\d{1,2})/', CalendarHandler),
    (br'/smiley/(\w+)\.gif', SmileyHandler),
    (br'/(rss|atom)\.xml', RssHandler),
    (br'/robots\.txt', RobotsHandler),
    (br'/.*', NotFoundHandler),
]
