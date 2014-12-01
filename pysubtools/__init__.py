from __future__ import absolute_import

from zipfile import ZipExtFile

from .subtitle import Subtitle, SubtitleUnit
from .parsers import BaseParser, EncodingError, NoParserError, ParserError
from .parsers.encodings import guess_from_lang

def load(data, **kwargs):
  if not isinstance(data, (file, ZipExtFile)):
    raise TypeError("Data needs to be a file object, it is '{}'".format(type(data)))

  return loads(data.read(), **kwargs)

def loads(data, **kwargs):
  if type(data) is not str:
    raise TypeError("Data needs to be a str object, it is '{}'".format(type(data)))

  parser = BaseParser.load(data, **kwargs)
  return parser

__all__ = [
  'Subtitle',
  'SubtitleUnit',
  'load',
  'loads',
  'guess_from_lang',
  'EncodingError',
  'NoParserError',
  'ParserError',
]
