import enum
import math
import random

from huhhttp.fusil.auto_mangle import AutoMangle
from huhhttp.fusil.mangle import MangleConfig, Mangle


CODEC_NAME_ALIASES = {
    'mac_roman': 'macintosh',
    'shift_jis': 'x-sjis',
}  # from beautifulsoup

CODEC_NAMES_ALL = (
    'ascii',
    'big5',
    'big5hkscs',
    'cp037',
    'cp424',
    'cp437',
    'cp500',
    'cp720',
    'cp737',
    'cp775',
    'cp850',
    'cp852',
    'cp855',
    'cp856',
    'cp857',
    'cp858',
    'cp860',
    'cp861',
    'cp862',
    'cp863',
    'cp864',
    'cp865',
    'cp866',
    'cp869',
    'cp874',
    'cp875',
    'cp932',
    'cp949',
    'cp950',
    'cp1006',
    'cp1026',
    'cp1140',
    'cp1250',
    'cp1251',
    'cp1252',
    'cp1253',
    'cp1254',
    'cp1255',
    'cp1256',
    'cp1257',
    'cp1258',
    # 'cp65001',  # windows only
    'euc_jp',
    'euc_jis_2004',
    'euc_jisx0213',
    'euc_kr',
    'gb2312',
    'gbk',
    'gb18030',
    'hz',
    'iso2022_jp',
    'iso2022_jp_1',
    'iso2022_jp_2',
    'iso2022_jp_2004',
    'iso2022_jp_3',
    'iso2022_jp_ext',
    'iso2022_kr',
    'latin_1',
    'iso8859_2',
    'iso8859_3',
    'iso8859_4',
    'iso8859_5',
    'iso8859_6',
    'iso8859_7',
    'iso8859_8',
    'iso8859_9',
    'iso8859_10',
    'iso8859_13',
    'iso8859_14',
    'iso8859_15',
    'iso8859_16',
    'johab',
    'koi8_r',
    'koi8_u',
    'mac_cyrillic',
    'mac_greek',
    'mac_iceland',
    'mac_latin2',
    'mac_roman',
    'mac_turkish',
    'ptcp154',
    'shift_jis',
    'shift_jis_2004',
    'shift_jisx0213',
    'utf_32',
    'utf_32_be',
    'utf_32_le',
    'utf_16',
    'utf_16_be',
    'utf_16_le',
    'utf_7',
    'utf_8',
    'utf_8_sig',
)
EBCDIC = (
    'cp037',
    'cp424',
    'cp500',
    'cp875',
    'cp1026',
    'cp1140',
)
CODEC_NAMES = tuple(sorted(frozenset(CODEC_NAMES_ALL) - frozenset(EBCDIC)))
CHARSET_DECLARATIONS = (
    '',
    '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset={name}">',
    '<META HTTP-EQUIV=Content-Type CONTENT=text/html; charset={name}>',
    '<META CHARSET={name}>',
)
DOCTYPES = (
    '',
    '<!DOGTYPE>',
    '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN"'
    ' "http://www.w3.org/TR/html4/strict.dtd">',
    '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"'
    ' "http://www.w3.org/TR/html4/loose.dtd">',
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<!DOCTYPE html'
    ' PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"'
    ' "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">',
    '<!DOCTYPE html PUBLIC'
    ' "-//W3C//DTD XHTML 1.1//EN"'
    ' "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">',
    '<!DOCTYPE html>',
    '<!doctype html>',
    '<doctype html>',
)


class PeriodicGaussianFunction(object):
    def __init__(self, period=1.0):
        self.period = period

    def fract_value(self, x_value):
        # f(x) = 1∙exp(−((x−0.5)^2)/(2∙0.07^2)) + 0
        return math.exp(-(x_value - 0.5) ** 2 / 0.0098)

    def value(self, x_value):
        return self.fract_value((x_value / self.period) % 1.0)


class ConnectionAction(enum.Enum):
    close = 'close'
    reset = 'reset'


class CompressType(enum.Enum):
    gzip = 'gzip'
    not_gzip = 'not_gzip'
    gzip_broken = 'gzip_broken'
    deflate = 'deflate'
    raw_default = 'raw_deflate'


class Fuzzer(object):
    def __init__(self, seed=1, period=1000):
        self._rand = random.Random(seed)
        self._threshold_func = PeriodicGaussianFunction(period=period)
        self._counter = 0
        self._mangle_config = MangleConfig(rand=self._rand)
        self._auto_mangle = AutoMangle(self._mangle_config)

    @property
    def counter(self):
        return self._counter

    @counter.setter
    def counter(self, value):
        self._counter = value

    def _next_threshold(self):
        value = self._threshold_func.value(self._counter)
        self._counter += 1
        return value

    def session(self):
        counter = self._counter
        next_threshold = self._next_threshold()
        return FuzzSession(self._mangle_config, self._auto_mangle, self._rand,
                           next_threshold, counter)


class FuzzSession(object):
    def __init__(self, mangle_config, auto_mangle, rand, threshold, counter):
        self._mangle_config = mangle_config
        self._auto_mangle = auto_mangle
        self._rand = rand
        self._threshold = threshold
        self._counter = counter

    @property
    def threshold(self):
        return self._threshold

    @property
    def counter(self):
        return self._counter

    def connection_action(self):
        if self._rand.random() < self._threshold * 0.05:
            num = random.randint(1, 2)
            if num == 1:
                return ConnectionAction.close
            elif num == 2:
                return ConnectionAction.reset

    def hang_time(self):
        if self._rand.random() < self._threshold:
            return random.triangular(0.1, 1, 0)

    def compress_type(self, requested=None):
        rand_val = self._rand.random()

        if requested or rand_val < self._threshold:
            if self._threshold > 0.5:
                return self._rand.choice(tuple(CompressType))
            elif requested:
                if 'gzip' in requested:
                    return CompressType.gzip
                else:
                    return CompressType.deflate
            else:
                return CompressType.gzip

    def mangle(self, data):
        if self._counter % 5 != 0:
            return data

        self._auto_mangle.aggressivity = self._threshold * 0.75
        self._auto_mangle.setupConf(data)
        mangler = Mangle(self._mangle_config, bytearray(data))
        mangler.run()
        return mangler.data

    def codec(self):
        if self._rand.random() < 0.25:
            codec_name = self._rand.choice(CODEC_NAMES)

            if self._rand.random() < self._threshold:
                codec_name_2 = self._rand.choice(CODEC_NAMES)
            else:
                codec_name_2 = codec_name

            encoding_name = codec_name_2.upper().replace('_', '-')

            if codec_name_2 in CODEC_NAME_ALIASES:
                if self._rand.random() < self._threshold:
                    encoding_name = CODEC_NAME_ALIASES[codec_name_2]\
                        .upper().replace('_', '-')

            return (codec_name, encoding_name)
        else:
            return ('utf_8', 'UTF-8')

    def charset(self):
        return self._rand.choice(CHARSET_DECLARATIONS)

    def doctype(self):
        if self._rand.random() < 0.5:
            return self._rand.choice(DOCTYPES)
        else:
            return '<!DOCTYPE html>'
