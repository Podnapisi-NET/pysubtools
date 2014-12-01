from __future__ import absolute_import

from pyparsing import *
import re

from .base import BaseParser, ParserError

class SubRipParser(BaseParser):
  """Parser for SubRip.
  """
  FORMAT = 'SubRip'
  FORMAT_RE = re.compile(r'^\s*\d+:\d+:\d+[.,]\d+\s+-->\s+\d+:\d+:\d+[.,]\d+\s*$', re.M)

  def is_it(self):
    return bool(self.FORMAT_RE.search(self._data))

  def __init__(self, *args, **kwargs):
    super(SubRipParser, self).__init__(*args, **kwargs)

    ParserElement.setDefaultWhitespaceChars(' \t')

    # Suppress line starts endings
    SOL = lineStart.suppress()
    EOL = lineEnd.suppress()
    EOF = stringEnd.suppress()

    # Some forward declarations
    header = Forward()

    # Some basic elements
    colon = Literal(':').suppress()
    line_separator = Literal('|').suppress()
    arrow = Literal('-->').suppress()
    sequence_number = SOL + Word(nums).setParseAction(lambda x: int(x[0])) + EOL + Optional(OneOrMore(EOL).setParseAction(
      self.add_warning('Empty lines after sequence, ignoring')
    ))
    sequence_number = sequence_number.setResultsName('sequence')
    time = Regex(r'(?P<hours>\d{2}):(?P<minutes>\d{2}):(?P<seconds>\d{2},\d{3})').setParseAction(
      lambda x: int(x['hours']) * 3600 + int(x['minutes']) * 60 + float(x['seconds'].replace(',', '.'))
    ) | Regex(r'(?P<hours>\d{2}):(?P<minutes>\d{2}):(?P<seconds>\d{2}\.\d{3})').setParseAction(
      lambda x: int(x['hours']) * 3600 + int(x['minutes']) * 60 + float(x['seconds'])
    ).addParseAction(self.add_warning('Used dot notation for fixed point'))
    position = Regex(r'X1:(?P<x1>\d+)\s+X2:(?P<x2>\d+)\s+Y1:(?P<y1>\d+)\s+(?P<y2>\d+)')
    position = position.setParseAction(
      lambda x: ((int(x['x1']), int(x['y1'])),
                (int(x['x2']), int(x['y2'])))
    ).setResultsName('position')
    duration = time.setResultsName('start') - arrow - time.setResultsName('end')
    duration = duration.setResultsName('time')
    text_line = Regex(r'[^|\n\r]+') | Empty().setParseAction(self.add_warning('Empty line'))
    text_line = text_line.setParseAction(lambda x: unicode(x[0] if x else '').rstrip())

    # Composite
    header << sequence_number - duration - Optional(position) + EOL
    header = header.setResultsName('header')
    line = NotAny((EOL + header) | EOF) + SOL.leaveWhitespace() + text_line + Optional(line_separator + text_line) + EOL
    text = Group(OneOrMore(line)) |\
           FollowedBy(EOL | EOF).setParseAction(self.add_warning('Empty subtitle unit, ignoring it'))
    text = text.setResultsName('text')
    unit = Group(header - text)

    # Final parser
    self._parser = ZeroOrMore(EOL) + OneOrMore(unit + (EOL | Empty().addParseAction(
      self.add_warning('Missing empty line after unit.')
    ))) + Optional(ZeroOrMore(EOL))

  def parse(self, **kwargs):
    try:
      self.parsed = self._parser.parseString(self._data, parseAll = True)
    except (ParseException, ParseSyntaxException), e:
      raise ParserError(e.lineno, e.col, e.line, str(e))

    # TODO finish it up
    # Add warnings about sequences
