import asyncio
import calendar
import collections
import email.utils
import html
import logging
import os.path
import re
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
    ATOM_TEMPLATE


_logger = logging.getLogger(__name__)


class SiteServer(Server):
    def __init__(self, fuzzer, restart_interval=10000):
        super().__init__(HANDLERS)
        self.fuzzer = fuzzer
        self.restart_interval = restart_interval
        self.asyncio_server = None


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

        self._fuzz = self.server.fuzzer.session()
        _logger.info('Fuzz session: counter=%d threshold=%.04f',
                     self.server.fuzzer.counter, self._fuzz.threshold)

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
    def write_cms(self, status_code=200, reason=b'OK'):
        self.stream()
        yield from self.write_header(
            status_code, reason, headers={b'Content-Type': b'text/html'})
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


class SmokeTestHandler(SiteHandler):
    @asyncio.coroutine
    def process(self):
        yield from self.write_header(200, b'OK')
        yield from self.write_content(b'It looks ok!')


class HomeHandler(SiteHandler):
    def get_body(self):
        return INDEX_CONTENT


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
    def _big_header(self):
        yield from self.write(b'HTTP/1.0 200\r\n')
        for dummy in range(100):
            yield from self.write(b'A' * 10000)
        yield from self.write(b': A\r\n')
        yield from self.write(b'Content-Length: 0\r\n\r\n')

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
            'jokes2': self._big_header,
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
    (br'/wirdpress/page/web_ring', WebRingPageHandler),
    (br'/wirdpress/calendar/(\d{4})/(\d{1,2})/(\d{1,2})/', CalendarHandler),
    (br'/smiley/(\w+)\.gif', SmileyHandler),
    (br'/(rss|atom)\.xml', RssHandler),
    (br'/robots\.txt', RobotsHandler),
    (br'/.*', NotFoundHandler),
]
