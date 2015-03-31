from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import codecs
import chardet

invalid_chars = u'\x9e'
similar_encodings = {
  'ISO-8859-2': ['windows-1250'],
  'windows-1255': ['windows-1256'],
  'GB2312': ['GB18030'],
  # Just a try
  'EUC-TW': ['BIG5-TW'],
}

class EncodingError(Exception):
  def __init__(self, message, tried_encodings = [], *args, **kwargs):
    self.tried_encodings = tried_encodings
    super(EncodingError, self).__init__(message, *args, **kwargs)

def guess_from_lang(lang):
  """Specify ISO-639-1 language to guess probable encoding."""
  guesses = {
    'sl': ['windows-1250'],
    'ko': ['euckr'],
    'ja': ['sjis'],
    'ar': ['windows-1256'],
    'el': ['windows-1253'],
    'zh': ['big5'],
    'he': ['windows-1255'],
    'ru': ['koi8-r'],
    'es': ['windows-1252'],
    'fr': ['windows-1252'],
    'bg': ['windows-1251'],
    'mk': ['windows-1251'],
    'th': ['windows-874'],
    'uk': ['koi8-u'],
    'sr': ['windows-1251'],
    'vi': ['windows-1258'],
    'fa': ['windows-1256'],
    'fi': ['iso8859-15'],
    'es': ['iso8859-15'],
  }

  # Revert to chardet
  return guesses.get(lang, [])

def can_decode(data, encoding):
  reader = None
  proper = False
  try:
    reader = io.TextIOWrapper(data, encoding, newline = '')
    proper = True
    # Go through data
    for line in reader:
      for char in invalid_chars:
        if char in line:
          proper = False
          break
  except (UnicodeDecodeError, LookupError):
    proper = False

  if reader:
    reader.detach()
  data.seek(0)
  return proper

def detect(data, encoding = None, language = None):
  """
  Tries to detect encoding for specified 'data'. Will return a tuple (encoding, confidence).
  Confidence may be None, which means the encoding was detected from provided language or
  encoding hint, or it stumbled over a unicode BOM.
  """
  if not isinstance(data, (io.BytesIO, io.BufferedReader)):
    raise TypeError("Needs to be a buffered file object.")

  tried_encodings = set()

  # Check for BOM (100% confidence)
  test_data = data.read(8)
  data.seek(0)
  if test_data.startswith(codecs.BOM_UTF8):
    return 'utf-8-sig', None
  elif test_data.startswith(codecs.BOM_UTF16):
    return 'utf16', None

  encodings = []
  if encoding:
    encodings.append(encoding)
  if language:
    encodings += guess_from_lang(language)

  # Autodetect encoding
  detected = chardet.detect(data.read())
  data.seek(0)
  if detected and detected['encoding']:
    encodings.append((detected['encoding'], detected['confidence']))
  if not encodings:
    raise EncodingError("Have no clue where to start.")

  # Reverse order
  encodings.reverse()
  while True:
    encoding = encodings.pop()
    if can_decode(data, encoding if not isinstance(encoding, tuple) else encoding[0]):
      # We've found it!
      break
    tried_encodings.add(encoding if not isinstance(encoding, tuple) else encoding[0])

    similar = similar_encodings.get(encoding if not isinstance(encoding, tuple) else encoding[0])
    if similar:
      encodings += list(set(similar).difference(tried_encodings))
    if not encodings:
      # We lost :(
      raise EncodingError("Could not detect proper encoding", list(tried_encodings))

  if not isinstance(encoding, tuple):
    encoding = (encoding, None)

  return encoding
