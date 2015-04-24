from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import re
import io
from state_machine import acts_as_state_machine, before, after,\
                          State, Event, InvalidStateTransition

from .base import Parser

@acts_as_state_machine
class SubRipStateMachine(object):
  name = 'SubRip State machine'

  class Skip(Exception):
    pass

  # Let us define some states
  start = State(initial = True)
  unit = State()
  unit_text = State()
  finished = State()

  # And events
  found_sequence   = Event(from_states = [start], to_state = unit)
  found_header     = Event(from_states = [unit, unit_text, start], to_state = unit_text)
  found_text       = Event(from_states = [unit_text, start], to_state = unit_text)
  skip_sequence    = Event(from_states = [unit_text, start], to_state = unit_text)
  found_empty      = Event(from_states = [unit_text, start, unit], to_state = start)
  done             = Event(from_states = [unit, unit_text, start], to_state = finished)

  # Regular expressions
  # Components
  _time = re.compile(r'(?:\d{1,2}:){2}\d{1,2},\d{1,3}')

  # Parts of unit
  _sequence = re.compile(r'^\s*\d+\s*$')
  _header = re.compile(r'^\s*([0-9:,.]+\s*-->\s*[0-9:,.]+)\s*(.*)$')
  _tagged_header = re.compile(r'^\{([^}]*)\}')

  # Tagged properties
  _tag_position = re.compile(r'\s*\\pos\(\s*(\d+)\s*,\s*(\d+)\s*\)\s*')

  def __init__(self, parser):
    self.parser = parser
    self._parsed = None
    self.temp = None
    self.paused = False

  @property
  def read_lines(self):
    return self.parser._read_lines

  @property
  def current_line_num(self):
    return self.parser._current_line_num

  @property
  def current_line(self):
    return self.parser._current_line

  @current_line.setter
  def current_line(self, value):
    self.parser._current_line = value

  def next_line(self):
    return self.parser._next_line()

  def fetch_line(self, line):
    return self.parser._fetch_line(line)

  def pause(self):
    # Pauses for one iteration
    self.paused = True

  def need_pause(self):
    p = self.paused
    self.paused = False
    return p

  # Main iteration
  def iterate(self):
    # Main loop that decides what to do
    if not self.need_pause():
      if not self.next_line():
        self.done()
        return

    if not self.current_line.strip():
      self.found_empty()
      return
    if self.is_start:
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
    previous_seq = self.temp['sequence'] if self.temp else 0

    sequence = int(self.current_line.strip())
    if sequence - previous_seq != 1:
      self.pause()
      self.current_line = str(previous_seq + 1)
      self.parser.add_warning(self.current_line_num + 1, 1, self.fetch_line(self.current_line_num), "Sequence number out of sync")
      raise self.Skip

    if self.current_state == self.unit_text:
      # We need to remove last empty line
      del self.temp['data']['lines'][-1]

  @after('found_sequence')
  def create_unit(self):
    self._parsed = self.temp
    self.temp = {
      'sequence': int(self.current_line.strip()),
      'data': {
        'lines': []
      },
    }

  @before('found_header')
  def validate_header(self):
    if self.is_unit_text:
      self.parser.add_warning(self.current_line_num + 1, 1, self.current_line, "Duplicated time information, ignoring.")
      raise self.Skip
    if self.is_start:
      self.skip_sequence()
      self.parser.add_warning(self.current_line_num + 1, 1, self.current_line, "New unit starts without a sequence.")
      raise self.Skip

    if '.' in self.current_line:
      # Stay on same line
      self.pause()
      original = self.fetch_line(self.current_line_num)
      col = self.current_line.index('.')
      self.current_line = self.current_line.replace('.', ',', 1)
      self.parser.add_warning(self.current_line_num + 1, col + 1, original, 'Used dot as decimal separator instead of comma.')
      raise self.Skip
    # Re-check header
    m = self._header.match(self.current_line)
    if m.group(2):
      original = self.fetch_line(self.current_line_num)
      # Found garbage
      column = self.current_line.index(m.group(2)) + 1
      self.current_line = m.group(1)
      # Re-try
      self.pause()
      self.parser.add_warning(self.current_line_num + 1, column, original, 'Header has unrecognized content at the end.')
      raise self.Skip

    # Check it
    start, end = self.current_line.split('-->')
    start = self._time.match(start.strip())
    end = self._time.match(end.strip())

    if not start or not end:
      self.parser.add_error(self.current_line_num + 1, 1, self.fetch_line(self.current_line_num), "Could not parse timings.")
      raise self.Skip

    return True

  @after('found_header')
  def parse_time(self):
    # It is safe to do it now
    start, end = self.current_line.split('-->')
    start = self._time.match(start.strip())
    end = self._time.match(end.strip())

    start, end = start.group(0).split(':'), end.group(0).split(':')

    convert = lambda x: int(x[0]) * 3600 + int(x[1]) * 60 + float(x[2].replace(',', '.'))
    self.temp['data'].update(dict(
      start = convert(start),
      end = convert(end)
    ))

  @after('skip_sequence')
  def fix_sequence_skip(self):
    self._parsed = self.temp
    self.temp = {
      'sequence': (self.temp['sequence'] if self.temp else 0) + 1,
      'data': {
        'lines': []
      },
    }
    self.parse_time()

  @before('found_text')
  def validate_text(self):
    if self.is_start:
      if self.temp:
        # Add empty line
        self.temp['data']['lines'] += [u'']
      else:
        self.parser.add_warning(self.current_line_num + 1, 1, self.current_line, "Junk before first unit.")
        raise self.Skip

  @after('found_text')
  def insert_text(self):
    # Check for tagged header inside text
    tagged = self._tagged_header.match(self.current_line)
    if tagged:
      # Remove it
      self.current_line = self.current_line[len(tagged.group(0)):]
      tagged = tagged.group(1)
      # Parse it further
      pos = self._tag_position.search(tagged)
      if pos:
        self.temp['data']['position'] = {
          'x': int(pos.group(1)),
          'y': int(pos.group(2))
        }
        tagged = tagged.replace(pos.group(0), '', 1)

    self.temp['data']['lines'] += [i.rstrip() for i in self.current_line.split('|')]

    # Unknown TAG headers
    if tagged:
      self.parser.add_warning(self.current_line_num + 1, 1, self.fetch_line(self.current_line_num), 'Tagged header not fully parsed.')
      raise self.Skip

  @before('found_empty')
  def validate_empty(self):
    if self.current_state == self.start:
      if self.temp:
        # Add empty line to text (since previous line was a text)
        self.temp['data']['lines'] += [u'']
      else:
        self.parser.add_warning(self.current_line_num + 1, 1, self.fetch_line(self.current_line_num), "Have empty line before first unit.")
        raise self.Skip
    elif self.is_unit:
      self.parser.add_warning(self.current_line_num + 1, 1, self.fetch_line(self.current_line_num), "Have empty line between sequence number and timings.")
      raise self.Skip

  @after('found_empty')
  def insert_empty(self):
    pass

  @before('done')
  def final_unit(self):
    self._missing_line = self.current_state != self.start

  @after('done')
  def final_unit(self):
    self._parsed = self.temp
    self.temp = None
    if self._missing_line:
      original = self.fetch_line(self.current_line_num)
      self.parser.add_warning(self.current_line_num + 1, len(self.current_line), original, 'Missing empty line after unit.')
      raise self.Skip

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
  FORMAT_RE = re.compile(r'^(?:[^:]+:){2}[^- ]+\s+-->\s+(?:[^:]+:){2}.*$')

  @classmethod
  def _can_parse(cls, data):
    # Go through first few lines
    can = False
    for i in range(0, 10):
      line = data.readline()
      if isinstance(line, bytes):
        line = line.decode('latin').replace('\x00', '')

      can = bool(cls.FORMAT_RE.search(line))
      if can:
        break
    data.seek(0)
    return can

  def _parse(self, **kwargs):
    machine = SubRipStateMachine(self)

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
      except SubRipStateMachine.Skip:
        # Just skip
        pass
      except InvalidStateTransition:
        self.add_error(machine.current_line_num + 1, 1, machine.current_line, "Unparsable line")
