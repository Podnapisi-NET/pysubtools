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

    # Part of the parser internals
    self._read_lines = []
    self._current_line_num = -1
    self._current_line = None

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

  def _parse_metadata(self):
    """Parses the subtitle metadata (if format has a header at all)."""
    return {}

  def parse(self, data = None, encoding = None, language = None, **kwargs):
    """Parses the file and returns the subtitle. Check warnings after the parse."""
    if data:
      # We have new data, discard old and set up for new
      self._data = self._normalize_data(data)
      # Check encoding
      self.encoding, self.encoding_confidence = encodings.detect(self._data, encoding = encoding, language = language)
      self._data.seek(0)
      # Wrap it
      self._data = io.TextIOWrapper(self._data, self.encoding, newline = '', errors = 'replace')


    # Create subtitle
    from .. import Subtitle, SubtitleUnit
    sub = Subtitle(**self._parse_metadata())
    for unit in self._parse(**kwargs):
      sub.append(SubtitleUnit(**unit['data']))
    return sub

  @staticmethod
  def from_data(data, encoding = None, language = None):
    """Returns a parser that can parse 'data' in raw string."""
    data = Parser._normalize_data(data)
    encoding, encoding_confidence = encodings.detect(data, encoding, language)
    data.seek(0)

    for parser in Parser.__subclasses__():
      if not parser.can_parse(data):
        continue
      parser = parser()
      parser._data = io.TextIOWrapper(data, encoding, newline = '', errors = 'replace')
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

  # Iteration methods
  def _previous_line(self):
    self._current_line_num -= 1
    self._data.seek(-self._read_lines[self._current_line_num], io.SEEK_CUR)
    self._current_line = self._data.readline().rstrip()

  def _next_line(self):
    line = self._data.readline()
    if not line:
      return False
    self._current_line_num += 1

    if len(self._read_lines) == self._current_line_num:
      self._read_lines.append(len(line))
    self._current_line = line

    return True

  def _fetch_line(self, line):
    if line > self._current_line_num:
      raise ValueError("Cannot seek forward.")

    offset = self._current_line_num - line
    offset = sum(self._read_lines[self._current_line_num - offset:self._current_line_num + 1])
    new_pos = self._data.seek(self._data.tell() - offset)
    line = self._data.readline().rstrip()
    self._data.seek(new_pos + offset)
    return line.rstrip()

  def _rewind(self):
    self._current_line_num = -1
    self._read_lines = []
    self._current_line = None
    self._data.seek(0)
