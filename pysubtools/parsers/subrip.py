from __future__ import absolute_import

import re
import io
from state_machine import acts_as_state_machine, before, after,\
                          State, Event, InvalidStateTransition

from .base import Parser, ParseError, ParseWarning

@acts_as_state_machine
class SubRipStateMachine(object):
  name = 'SubRip State machine'

  # Let us define some states
  start = State(initial = True)
  unit = State()
  unit_text = State()
  finished = State()

  # And events
  found_sequence   = Event(from_states = [start, unit_text], to_state = unit)
  found_header     = Event(from_states = [unit, unit_text], to_state = unit_text)
  found_text       = Event(from_states = [unit_text, start, unit], to_state = unit_text)
  skip_sequence    = Event(from_states = [unit_text], to_state = unit_text)
  done             = Event(from_states = unit_text, to_state = finished)

  # Regular expressions
  # Components
  _time = re.compile(r'(?:\d{2}:){2}\d{2},\d{3}')

  # Parts of unit
  _sequence = re.compile(r'^\s*\d+\s*$')
  _header = re.compile(r'^\s*[0-9:,.]+\s*-->\s*[0-9:,.]+\s*$')

  def __init__(self, data):
    self.data = data
    self._parsed = None
    self.temp = None
    self.paused = False

    self.read_lines = []
    self.current_line_num = -1
    self.current_line = None

  def pause(self):
    # Pauses for one iteration
    self.paused = True

  def need_pause(self):
    p = self.paused
    self.paused = False
    return p

  def previous_line(self):
    self.current_line_num -= 1
    self.data.seek(-self.read_lines[self.current_line_num], io.SEEK_CUR)
    self.current_line = self.data.readline().rstrip()

  def next_line(self):
    line = self.data.readline()
    if not line:
      return False
    self.current_line_num += 1

    if len(self.read_lines) == self.current_line_num:
      self.read_lines.append(len(line))
    self.current_line = line

    return True

  def fetch_line(self, line):
    if line > self.current_line_num:
      raise ValueError("Cannot seek forward.")

    offset = self.current_line_num - line
    offset = sum(self.read_lines[self.current_line_num - offset:self.current_line_num + 1])
    new_pos = self.data.seek(self.data.tell() - offset)
    line = self.data.readline().rstrip()
    self.data.seek(new_pos + offset)
    return line.rstrip()

  # Main iteration
  def iterate(self):
    # Main loop that decides what to do
    if not self.need_pause():
      if not self.next_line():
        self.done()
        return

    m = self._sequence.match(self.current_line)
    if m:
      self.found_sequence()
      return
    m = self._header.match(self.current_line)
    if m:
      self.found_header()
      return

    # We have text (presuming)
    self.found_text()

  @before('found_sequence')
  def validate_unit(self):
    if self.temp is None:
      return True

    sequence = int(self.current_line.strip())
    if sequence - self.temp['sequence'] != 1:
      self.pause()
      self.current_line = str(self.temp['sequence'] + 1)
      raise ParseWarning(self.current_line_num + 1, 1, self.fetch_line(self.current_line_num), "Sequence number out of sync")

  @after('found_sequence')
  def create_unit(self):
    if self.current_state == self.unit_text:
      # We need to remove last empty line
      del self.temp['lines'][-1]
    self._parsed = self.temp
    self.temp = {
      'sequence': int(self.current_line.strip()),
      'header': {
        'time': {}
      },
      'lines': []
    }

  @before('found_header')
  def validate_header(self):
    if self.current_state == self.unit_text:
      if self._header.match(self.current_line):
        raise ParseWarning(self.current_line_num + 1, 1, self.current_line, "Duplicated time information, ignoring.")
      else:
        self.skip_sequence()
        raise ParseWarning(self.current_line_num + 1, 1, self.current_line, "New unit starts without a sequence.")

    if '.' in self.current_line:
      # Stay on same line
      self.pause()
      original = self.fetch_line(self.current_line_num)
      col = self.current_line.index('.')
      self.current_line = self.current_line.replace('.', ',', 1)
      raise ParseWarning(self.current_line_num + 1, col + 1, original, 'Used dot as decimal separator instead of comma.')

    return True

  @after('found_header')
  def parse_time(self):
    start, end = self.current_line.split('-->')
    start = self._time.match(start.strip()).group(0).split(':')
    end = self._time.match(end.strip()).group(0).split(':')

    convert = lambda x: int(x[0]) * 3600 + int(x[1]) * 60 + float(x[2].replace(',', '.'))
    self.temp['header']['time'] = (convert(start), convert(end))

  @after('skip_sequence')
  def fix_sequence_skip(self):
    self._parsed = self.temp
    self.temp = {
      'sequence': self.temp['sequence'] + 1,
      'header': {
        'time': {}
      },
      'lines': []
    }
    self.parse_time()

  @before('found_text')
  def validate_text(self):
    if self.current_state == self.start and not self.current_line.strip():
      raise ParseWarning(self.current_line_num + 1, 1, self.fetch_line(self.current_line_num), "Have empty line before first unit.")
    if self.current_state == self.unit and not self.current_line.strip():
      raise ParseWarning(self.current_line_num + 1, 1, self.fetch_line(self.current_line_num), "Have empty line between sequence number and timings.")

    if self.current_state not in (self.unit_text,):
      raise InvalidStateTransition

  @after('found_text')
  def insert_text(self):
    self.temp['lines'] += [i.rstrip() for i in self.current_line.split('|')]

  @after('done')
  def final_unit(self):
    self._parsed = self.temp
    self.temp = None
    if self.current_line.strip():
      original = self.fetch_line(self.current_line_num)
      raise ParseWarning(self.current_line_num + 1, len(self.current_line), original, 'Missing empty line after unit.')
    else:
      # Remove last empty line
      del self._parsed['lines'][-1]

  def parsed(self):
    if not self._parsed:
      return None
    parsed = self._parsed
    self._parsed = None
    return parsed

class SubRipParser(Parser):
  """Parser for SubRip.
  """
  FORMAT = 'SubRip'
  FORMAT_RE = re.compile(r'^\s*\d+:\d+:\d+[.,]\d+\s+-->\s+\d+:\d+:\d+[.,]\d+\s*$', re.M)

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

  def _parse(self, **kwargs):
    machine = SubRipStateMachine(self._data)

    # We have a state machine. Let us start.
    while True:
      try:
        if machine.current_state != machine.finished:
          machine.iterate()
        parsed = machine.parsed()
        if parsed:
          yield parsed
        if machine.current_state == machine.finished:
          break
      except ParseWarning, e:
        self.add_warning(e)
      except InvalidStateTransition:
        raise ParseError(machine.current_line_num, 1, machine.current_line, "Got invalid state transition in {},"
                         " report as bug to developers!".format(machine.current_state))
