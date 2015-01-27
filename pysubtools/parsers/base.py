from __future__ import absolute_import

import io
import functools

from . import encodings

class NoParserError(Exception):
  pass

class ParseError(Exception):
  def __init__(self, line_number, column, line, description):
    self.line_number = line_number
    self.column = column
    self.line = line
    self.description = description
    super(ParseError, self).__init__(self.description)

  def __str__(self):
    return str(unicode(self))

  def __unicode__(self):
    return u"Parse error on line {} at column {} error occurred '{}'".format(
      self.line_number,
      self.column,
      self.description
    )

class ParseWarning(ParseError):
  def __unicode__(self):
    return "Parse warning on line {} at column {} warning occurred '{}'".format(
      self.line_number,
      self.column,
      self.description
    )

class Parser(object):
  """Abstract class for all parsers.
  """
  _subtitle = None
  parsed = None
  encoding = None
  encoding_confidence = None

  def __init__(self):
    self.warnings = []

  def parse(self, **kwargs):
    """Does the actual parsing.
    """
    raise NotImplementedError

  def add_warning(self, e):
    self.warnings.append({
      'line_number': int(e.line_number),
      'col': int(e.column),
      'line': unicode(e.line),
      'description': unicode(e.description)
    })

  @staticmethod
  def _normalize_data(data):
    if isinstance(data, str):
      data = io.BytesIO(data)
    elif isinstance(data, file):
      data = io.BufferedReader(io.FileIO(data.fileno(), closefd = False))
    elif not isinstance(data, (io.BytesIO, io.BufferedReader)):
      raise TypeError("Needs to be a file object or raw string.")
    data.seek(0)
    return data

  @classmethod
  def can_parse(cls, data):
    data = cls._normalize_data(data)
    return cls._can_parse(data)

  @classmethod
  def _can_parse(cls, data):
    """Needs to be reimplemented to quickly check if file seems the proper format."""
    raise NotImplementedError

  def _parse(self):
    """
    Parses the file, it returns a list of units in specified format. Needs to be
    implemented by the parser. It can also be a generator (yield)
    """
    raise NotImplementedError

  def parse(self, data = None, encoding = None, language = None):
    """Parses the file and returns the subtitle. Check warnings after the parse."""
    if data:
      # We have new data, discard old and set up for new
      self._data = self._normalize_data(data)
      if encoding is None:
        self.encoding, self.encoding_confidence = encodings.detect(self._data, language = language)
        self._data.seek(0)
      else:
        self.encoding_confidence = None
      # Wrap it
      self._data = io.TextIOWrapper(self._data, self.encoding, newline = '')

    # Create subtitle
    from .. import Subtitle, SubtitleUnit
    sub = Subtitle()
    for unit in self._parse():
      start, end = unit['header']['time']
      sub.append(SubtitleUnit(start, end, unit['lines'], **unit.get('meta', {})))
    sub.order()
    return sub

  @staticmethod
  def from_data(data, encoding = None, language = None):
    """Returns a parser that can parse 'data' in raw string."""
    data = Parser._normalize_data(data)
    if encoding is None:
      encoding, encoding_confidence = encodings.detect(data, encoding, language)
      data.seek(0)
    else:
      encoding_confidence = None

    for parser in Parser.__subclasses__():
      if not parser.can_parse(data):
        continue
      parser = parser()
      parser._data = io.TextIOWrapper(data, encoding, newline = '')
      parser.encoding = encoding
      parser.encoding_confidence = encoding_confidence
      return parser
    raise NoParserError("Could not find parser.")

  @staticmethod
  def from_format(format):
    """Returns a parser with 'name'."""
    for parser in Parser.__subclasses__():
      if parser.FORMAT == format:
        return parser()
    raise NoParserError("Could not find parser.")
