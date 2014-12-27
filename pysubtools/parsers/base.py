from __future__ import absolute_import

import chardet
import codecs
import io
import functools

class EncodingError(Exception):
  def __init__(self, message, tried_encodings = [], *args, **kwargs):
    self.tried_encodings = tried_encodings
    super(EncodingError, self).__init__(message, *args, **kwargs)

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
  _invalid_chars = u'\x9e'
  _similar_encodings = {
    'ISO-8859-2': 'windows-1250'
  }

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

  @staticmethod
  def is_proper(data, encoding):
    reader = io.TextIOWrapper(data, encoding, newline = '')
    proper = True
    reader.seek(0)
    # Go through data
    for line in reader:
      for char in Parser._invalid_chars:
        if char in line:
          proper = False
          break
    reader.detach()
    data.seek(0)
    return proper

  def _parse(self):
    """
    Parses the file, it returns a list of units in specified format. Needs to be
    implemented by the parser. It can also be a generator (yield)
    """
    raise NotImplementedError

  @staticmethod
  def detect_encoding(data, encoding = None):
    data = Parser._normalize_data(data)
    # Read first 5 kiB of subtitle file for chardet
    test_data = data.read(5 * 1024)
    data.seek(0)

    encoding_confidence = None
    tried_encodings = []

    # Check for BOM
    has_bom = False
    if test_data.startswith(codecs.BOM_UTF8):
      encoding = 'utf-8-sig'
      has_bom = True
    elif test_data.startswith(codecs.BOM_UTF16):
      encoding = 'utf16'
      has_bom = True

    # Test if the encoding is really proper
    if not has_bom and encoding and not isinstance(encoding, list):
      encoding = [encoding]

    if encoding is None:
      # Autodetect encoding
      encoding = chardet.detect(test_data)
      encoding_confidence = encoding['confidence']
      encoding = encoding['encoding']
      tried_encodings.append(encoding)
    if encoding is None:
      raise EncodingError("Could not detect proper encoding", tried_encodings)

    while not Parser.is_proper(data, encoding):
      tried_encodings.append(encoding)
      encoding = Parser._similar_encodings.get(encoding)
      if not encoding:
        # We lost :(
        e.tried_encodings = tried_encodings
        raise EncodingError("Could not detect proper encoding", tried_encodings)

    return encoding, encoding_confidence

  def parse(self, data = None, encoding = None):
    """Parses the file and returns the subtitle. Check warnings after the parse."""
    if data:
      # We have new data, discard old and set up for new
      self._data = self._normalize_data(data)
      self.encoding, self.encoding_confidence = self.detect_encoding(self._data, encoding)
      self._data.seek(0)
      # Wrap it
      self._data = io.TextIOWrapper(self._data, self.encoding, newline = '')

    # Create subtitle
    from .. import Subtitle, SubtitleUnit
    sub = Subtitle()
    for unit in self._parse():
      start, end = unit['header']['time']
      sub.add_unit(SubtitleUnit(start, end, unit['lines']))
    sub.order()
    return sub

  @staticmethod
  def from_data(data, encoding = None):
    """Returns a parser that can parse 'data' in raw string."""
    data = Parser._normalize_data(data)
    encoding, encoding_confidence = Parser.detect_encoding(data, encoding)
    data.seek(0)
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
