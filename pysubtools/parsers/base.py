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

class ParserError(Exception):
  def __init__(self, line_number, column, line, error):
    self.line_number = line_number
    self.column = column
    self.line = line
    self.error = error
    super(ParserError, self).__init__(self.error)

  def mark_error(self):
    output = self.line
    output += u'\n' + u' ' * (self.column - 1) + u'^'
    return output

  def __str__(self):
    return "Parse error on line {} at column {} error occurred '{}'".format(
      self.line_number,
      self.column,
      self.error
    )

class BaseParser(object):
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

  def __init__(self, data, encoding, encoding_confidence = None):
    self._data = data
    self.encoding = encoding
    self.encoding_confidence = encoding_confidence
    self.warnings = []
    self._warnings_lines = set([])

  def parse(self, **kwargs):
    """Does the actual parsing.
    """
    raise NotImplementedError

  def add_warning(self, warning, exclude = True):
    return functools.partial(self._add_warning, warning = warning, exclude = exclude)

  def _add_warning(self, s, loc, toks, warning, exclude):
    from pyparsing import lineno, col, line

    # With backtracking, warnings can multiply
    key = (lineno(loc, s), col(loc, s), warning)
    if key in self._warnings_lines:
      return

    self.warnings.append({
      'line_number': key[0],
      'col': key[1],
      'line': line(loc, s),
      'warning': key[2]
    })
    self._warnings_lines.add(key)

  def is_it(self):
    """Needs to be reimplemented to quickly check if file seems the proper format.
    """
    raise NotImplementedError

  @staticmethod
  def is_proper(data, encoding):
    for char in BaseParser._invalid_chars:
      if char in data:
        raise EncodingError("Could not decode with '{}'".format(encoding))

  @staticmethod
  def load(data, format = None, encoding = None, **kwargs):
    """Parses data in raw string.
    Any additional parameter is passed to the importer.

    Parameters:
      format - Specify format to use, if set to None it will try all of them.
      encoding - Specify which encoding to use, defaults to autodetect (None)
    """
    encoding_confidence = None
    tried_encodings = []
    if type(data) is not str:
      raise TypeError("Data needs to be a 'str', not '{}'".format(type(data)))

    # Check for BOM
    has_bom = False
    if data.startswith(codecs.BOM_UTF8):
      encoding = 'utf-8-sig'
      has_bom = True
    elif data.startswith(codecs.BOM_UTF16):
      encoding = 'utf16'
      has_bom = True

    # Test if the encoding is really proper
    if not has_bom and encoding and not isinstance(encoding, list):
      encoding = [encoding]

    # Select proper encoding from a list of encodings
    if isinstance(encoding, list):
      encodings = encoding
      encoding = None
      for enc in encodings:
        try:
          tried_encodings.append(enc)
          tmp = data.decode(enc)
          BaseParser.is_proper(tmp, enc)
          data = tmp
          encoding = enc
          break
        except (UnicodeDecodeError, EncodingError):
          pass

    if encoding is None:
      # Autodetect encoding
      encoding = chardet.detect(data)
      encoding_confidence = encoding['confidence']
      encoding = encoding['encoding']
      tried_encodings.append(encoding)
    if encoding is None:
      raise EncodingError("Could not detect proper encoding", tried_encodings)

    while not isinstance(data, unicode):
      try:
        tmp = data.decode(encoding)
        BaseParser.is_proper(tmp, encoding)
        data = tmp
      except EncodingError, e:
        tried_encodings.append(encoding)
        encoding = BaseParser._similar_encodings.get(encoding)
        if not encoding:
          # We lost :(
          e.tried_encodings = tried_encodings
          raise e
      except UnicodeDecodeError:
        tried_encodings.append(encoding)
        raise EncodingError("Could not detect proper encoding", tried_encodings)

    for parser in BaseParser.__subclasses__():
      if format is None or format and format == parser.FORMAT:
        parser = parser(data, encoding, encoding_confidence)
        if not parser.is_it():
          continue
        parser.parse(**kwargs)
        return parser
    raise NoParserError("Could not find parser.")
