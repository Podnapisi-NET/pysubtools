from __future__ import absolute_import

def guess_from_lang(lang):
  """Specify ISO-639-1 language to guess probable encoding.
  """
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
    'bg': ['windows-1251'],
    'mk': ['windows-1251'],
    'th': ['windows-874'],
    'uk': ['koi8-u'],
    'sr': ['windows-1251'],
    'vi': ['windows-1258'],
    'fa': ['windows-1256'],
  }

  # Revert to chardet
  return guesses.get(lang, [])
