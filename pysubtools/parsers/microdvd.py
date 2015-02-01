from __future__ import absolute_import

import re

from .base import Parser, ParseError, ParseWarning
from ..subtitle import Frame

class MicroDVDParser(Parser):
  """Parser for SubRip.
  """
  FORMAT = 'MicroDVD'
  FORMAT_RE = re.compile(r'^\{(?P<start>\d+)\}\{(?P<end>\d+)\}(?P<header>\{[^}]\})*(?P<text>.+)$', re.M)
  HEADER_RE = re.compile(r'^\{DEFAULT\}(?P<header>\{[^}]+\})*$')

  @classmethod
  def _can_parse(cls, data):
    # Go through first few lines
    can = False
    for i in range(0, 10):
      line = data.readline()
      can = bool(cls.FORMAT_RE.search(line))
      if can:
        break
    data.seek(0)
    return can

  def _parse_header(self, header):
    return {}

  def parse_metadata(self):
    # TODO Parse possible default header
    return {}

  def _parse(self, fps = None, **kwargs):
    # TODO Add FPS heuristic (first line as fps)

    i = 0
    for line in self._data:
      m = self.FORMAT_RE.match(line.strip())
      if not m:
        self.add_error(i + 1, 1, line, "Could not parse line")
      else:
        start, end = int(m.group('start')), int(m.group('end'))
        if fps:
          start /= float(fps)
          end   /= float(fps)
        else:
          start, end = Frame(start), Frame(end)
        # Parse unit
        data = {
          'start': start,
          'end': end,
          'lines': m.group('text').split('|'),
         }
        # Parse header
        data.update(self._parse_header(m.groupdict().get('header', '')))
        # Pass along the unit data
        yield {
          'data': data
        }

      i += 1
