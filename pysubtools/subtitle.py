from __future__ import absolute_import

import io
import yaml

class HumanTime(yaml.YAMLObject):
  yaml_loader = yaml.SafeLoader
  yaml_dumper = yaml.SafeDumper

  yaml_tag = u'!human_time'

  def __init__(self, hours = 0, minutes = 0, seconds = 0.):
    self.hours   = hours
    self.minutes = minutes
    self.seconds = seconds

  @classmethod
  def from_yaml(cls, loader, node):
    value = loader.construct_scalar(node)
    return float(cls.from_string(value))

  @classmethod
  def to_yaml(cls, dumper, data):
    if isinstance(data, (int, float)):
      data = cls.from_seconds(data)

    return dumper.represent_scalar(u'!human_time', unicode(data))

  @classmethod
  def from_seconds(cls, time):
    obj = cls()
    obj.hours = int(time / 3600)
    time -= obj.hours * 3600
    obj.minutes = int(time / 60)
    time -= obj.minutes * 60
    obj.seconds = time
    return obj

  @classmethod
  def from_string(cls, time):
    obj = cls()

    if isinstance(time, basestring):
      time = time.split(':')
      obj.hours = int(time[0])
      obj.minutes = int(time[1])
      obj.seconds = float(time[2])
    else:
      raise TypeError("Unknown time format.")

    return obj

  def __unicode__(self):
    return u'{:02d}:{:02d}:{:06.3f}'.format(self.hours,
                                            self.minutes,
                                            self.seconds)

  def __float__(self):
    return self.to_seconds()

  def __int__(self):
    return int(self.to_seconds())

  def to_seconds(self):
    return self.hours * 3600 + self.minutes * 60 + self.seconds

class Frame(yaml.YAMLObject):
  yaml_loader = yaml.SafeLoader
  yaml_dumper = yaml.SafeDumper

  yaml_tag = u'!frame'

  def __init__(self, frame):
    self._frame = frame

  @classmethod
  def from_yaml(cls, loader, node):
    value = loader.construct_scalar(node)
    return cls(int(value))

  @classmethod
  def to_yaml(cls, dumper, data):
    if isinstance(data, int):
      data = cls(data)

    return dumper.represent_scalar(u'!frame', unicode(data._frame))

  def __int__(self):
    raise ValueError("Cannot convert frame to time without specified FPS.")

  def __float__(self):
    raise ValueError("Cannot convert frame to time without specified FPS.")

  def __eq__(self, value):
    return self._frame == value

  def __gt__(self, value):
    return self._frame > value

  def __lt__(self, value):
    return self._frame < value

  def __repr__(self):
    return 'Frame({})'.format(self._frame)

class SubtitleLine(object):
  """
  Class representing a line inside SubtitleUnit. It acts as an ordinary
  unicode objects, but has an ability to store additional metadata.
  """

  def __init__(self, text, **kwargs):
    self.text = text
    # Update with additional metadata
    self.__dict__.update(kwargs)

  def export(self):
    """Returns line in format for export."""
    output = dict(self.__dict__)
    text = output.pop('text', u'').encode('utf8')
    if not output:
      output = text
    else:
      output['text'] = text
    return output

  @classmethod
  def from_export(cls, obj):
    obj['text'] = obj.get('text', '').decode('utf-8')
    return cls(**obj)

  def __unicode__(self):
    return self.text

  def __repr__(self):
    d = dict(self.__dict__)
    text = d.pop('text', u'').encode('utf8')
    return "SubtitleLine({}{})".format(
      text,
      (', ' + ', '.join([' = '.join([k, unicode(v).encode('utf-8')]) for k, v in d.items()])) if d else ''
    )

  def __eq__(self, other):
    if not isinstance(other, SubtitleLine):
      return False
    return self.__dict__ == other.__dict__

  def __len__(self):
    return len(self.text)

class SubtitleLines(list):
  """Modified list class for special tratment of lines."""
  __slots__ = ()

  def __new__(cls, l = []):
    obj = super(SubtitleLines, cls).__new__(cls)
    for i in l:
      obj.append(i)
    return obj

  @staticmethod
  def _validate(value):
    if isinstance(value, unicode):
      value = SubtitleLine(value)
    if not isinstance(value, SubtitleLine):
      raise TypeError("Subtitle line needs to be unicode instead of '{}'".format(type(value)))
    return value

  def append(self, value):
    value = self._validate(value)
    super(SubtitleLines, self).append(value)

  def __setitem__(self, index, value):
    value = self._validate(value)
    super(SubtitleLines, self).__setattr__(index, value)

class SubtitleUnit(object):
  """Class for holding time and text data of a subtitle unit."""
  def __init__(self, start, end, lines = None, **meta):
    self.start = float(start) if not isinstance(start, Frame) else start
    self.end = float(end) if not isinstance(end, Frame) else end
    self._lines = SubtitleLines()

    self.__dict__.update(meta)

    if lines is not None:
      if not isinstance(lines, (list, set)):
        lines = list(lines)

      for line in lines:
        self._lines.append(line)

  def distance(self, other):
    """Calculates signed distance with other subtitle unit."""
    if not isinstance(other, SubtitleUnit):
      raise TypeError("Can calculate distance only with SubtitleUnit and not '{}'".format(type(other)))

    return other.start - self.start

  def __iter__(self):
    return self._lines.__iter__()

  def __setitem__(self, index, value):
    self._lines[index] = value

  def __getitem__(self, index):
    return self._lines[index]

  def append(self, value):
    self._lines.append(value)

  @property
  def lines(self):
    return map(unicode, self._lines)

  @property
  def duration(self):
    """Returns duration of subtitle unit in seconds."""
    return self.end - self.start

  @property
  def length(self):
    """Returns length of the SubtitleUnit (in characters)."""
    return sum((len(i) for i in self._lines))

  def move(self, distance):
    """Moves subtitle unit by 'distance' seconds."""
    if not isinstance(distance, (int, long, float)):
      raise TypeError("Need type of int, long or float instead of '{}'".format(type(distance)))
    self.start += distance
    self.end += distance

  def get_moved(self, distance):
    """Same as SubtitleUnit.move, just returns a copy while itself is unchanged."""
    clone = SubtitleUnit(**self.__dict__)
    clone.move(distance)
    return clone

  def stretch(self, factor):
    """Stretches the unit for 'factor'.
    """
    if not isinstance(factor, (int, long, float)):
      raise TypeError("Need type of int, long or float instead of '{}'".format(type(factor)))
    self.start *= factor
    self.end *= factor

  def get_stretched(self, factor):
    """Same as SubtitleUnit.stretch, just returns a copy while itself is unchanged."""
    clone = SubtitleUnit(**self.__dict__)
    clone.stretch(factor)
    return clone

  @property
  def meta(self):
    d = dict(self.__dict__)
    # Remove important part of metadata and lines
    d.pop('start')
    d.pop('end')
    d.pop('_lines')
    return d

  def __sub__(self, other):
    """See SubtitleUnit.get_moved."""
    if not isinstance(other, (int, long, float)):
      raise TypeError("Need type of int, long or float instead of '{}'".format(type(other)))
    return self.get_moved(-1 * other)

  def __add__(self, other):
    """See SubtitleUnit.get_moved."""
    return self.get_moved(other)

  def __isub__(self, other):
    """Same as SubtitleUnit.move."""
    if not isinstance(other, (int, long, float)):
      raise TypeError("Need type of int, long or float instead of '{}'".format(type(other)))
    self.move(-1 * other)

  def __iadd__(self, other):
    """Same as SubtitleUnit.move"""
    self.move(other)

  def __mul__(self, other):
    """See SubtitleUnit.get_stretched."""
    return self.get_stretched(other)

  def __imul__(self, other):
    """See SubtitleUnit.stretch."""
    self.stretch(other)

  def __eq__(self, other):
    if not isinstance(other, SubtitleUnit):
      raise TypeError("Can compare only with other SubtitleUnit, provided with '{}'".format(type(other)))

    return self.__dict__ == other.__dict__

  def __repr__(self):
    d = dict(self.__dict__)
    # Get known attributes
    start = d.pop('start')
    end = d.pop('end')
    lines = d.pop('_lines')
    return "SubtitleUnit({}, {}, {}, {})".format(start, end, lines, d)

  def to_dict(self, human_time = True):
    """Returns subtitle unit as a dict (with some human readable things)."""
    output = {}
    output.update(self.__dict__)
    # Overide custom attributes
    output['start'] = HumanTime.from_seconds(self.start) if human_time and not isinstance(self.start, Frame) else self.start
    output['end']   = HumanTime.from_seconds(self.end) if human_time and not isinstance(self.end, Frame) else self.end
    # And lines
    output['lines'] = [i.export() for i in self._lines]

    # Remove lines
    output.pop('_lines')
    return output

  @classmethod
  def from_dict(cls, input):
    """Creates SubtitleUnit from specified 'input' dict."""
    input = dict(input)
    return cls(
      lines = SubtitleLines([
        i.decode('utf-8') if isinstance(i, str) else i if isinstance(i, unicode) else SubtitleLine.from_export(i) for i in input.pop('lines', [])
      ]),
      **input
    )

class Subtitle(object):
  """
  The whole subtitle.

  To load a subtitle in non-native format, use parsers.Parser.from_data.
  """
  def __init__(self, units = [], **meta):
    self._units = []
    self.__dict__.update(meta)
    for unit in units:
      self.append(unit)

  def add_unit(self, unit):
    """Adds a new 'unit' and sorts the units. If adding many units, use append instead."""
    self.append(unit)
    self.order()

  def order(self):
    """Maintains order of subtitles."""
    self._units.sort(key = lambda x: x.start)

  def check_overlaps(self):
    """Checks for overlaps and returns them in list."""
    overlaps = []
    for current_unit in self._units[:-1]:
      i = self._units.index(current_unit)
      for next_unit in self._units[i + 1:]:
        if current_unit.end > next_unit.start:
          overlaps.append((i, self._units.index(next_unit)))
        else:
          break

    return overlaps

  def remove(self, unit):
    """Proxy for internal storage."""
    if not isinstance(unit, SubtitleUnit):
      raise TypeError("Can remove only SubtitleUnit, you passed '{}'".format(type(unit)))

    self._units.remove(unit)

  def index(self, unit):
    """Proxy for internal storage."""
    if not isinstance(unit, SubtitleUnit):
      raise TypeError("Can index only SubtitleUnit, you passed '{}'".format(type(unit)))

    return self._units.index(unit)

  def insert(self, index, unit):
    """Proxy for internal storage."""
    if not isinstance(unit, SubtitleUnit):
      raise TypeError("Can add only SubtitleUnit, you passed '{}'".format(type(unit)))

    return self._units.insert(index, unit)

  def append(self, unit):
    """Proxy for internal storage."""
    if not isinstance(unit, SubtitleUnit):
      raise TypeError("Can add only SubtitleUnit, you passed '{}'".format(type(unit)))

    return self._units.append(unit)

  def __getitem__(self, index):
    """Proxy for internal storage."""
    return self._units[index]

  def __setitem__(self, index, unit):
    """Proxy for internal storage."""
    if not isinstance(unit, SubtitleUnit):
      raise TypeError("Can add only SubtitleUnit, you passed '{}'".format(type(unit)))

    self._units[index] = unit

  def __delitem__(self, index):
    """Proxy for internal storage."""
    del self._units[index]

  def __len__(self):
    """Proxy for internal storage."""
    return len(self._units)

  def __iter__(self):
    """Proxy for internal storage."""
    return iter(self._units)

  def __reversed__(self):
    """Proxy for internal storage."""
    return reversed(self._units)

  def __eq__(self, other):
    """Proxy for internal storage."""
    return self.__dict__ == other.__dict__

  def __contains__(self, unit):
    """Proxy for internal storage."""
    # TODO make possible to test with string?
    return unit in self._units

  @property
  def meta(self):
    # Remove non-metadata from dict
    d = dict(self.__dict__)
    d.pop('_unit', None)
    return d

  @classmethod
  def from_dict(cls, data):
    """Creates Subtitle object from dict, parsed from YAML."""
    if data is None:
      data = {}
    data = dict(data)
    data['units'] = [SubtitleUnit.from_dict(i) for i in data.get('units') or []]
    return cls(**data)

  @classmethod
  def from_file(cls, input, multi = False):
    """
    Loads a subtitle from file in YAML format. If have multiple documents,
    set 'multi' to True. Do note, it loads _all_ subtitles at once.
    """
    if isinstance(input, basestring):
      input = io.BufferedReader(io.open(input, 'rb'))
    if isinstance(input, file):
      input = io.BufferedReader(io.FileIO(input.fileno(), closefd = False))
    if not isinstance(input, io.BufferedIOBase):
      raise TypeError("Load method accepts filename or file object.")
    input = io.TextIOWrapper(input)

    if multi:
      obj = cls.from_multi_yaml(input)
    else:
      obj = cls.from_yaml(input)

    # Detach wrapper
    input.detach()

    # Return our subtitle
    return obj

  @classmethod
  def from_yaml(cls, input):
    """Loads a subtitle from YAML format, uses safe loader."""
    # Construct a python dict
    data = yaml.safe_load(input)

    # Return our subtitle
    return cls.from_dict(data)

  @classmethod
  def from_multi_yaml(cls, input):
    """Loads multiple subtitles from YAML format, uses safe loader."""
    output = []
    for data in yaml.safe_load_all(input):
      output.append(cls.from_dict(data))

    # Return our subtitle
    return output

  def dump(self, output = None, human_time = True, allow_unicode = True):
    """Dumps this subtitle in YAML format with safe dumper."""
    # Construct a python dict
    obj = dict(self.__dict__)
    obj['units'] = [i.to_dict(human_time) for i in obj.pop('_units')]
    # Dump it
    return yaml.safe_dump(obj, output, encoding           = 'utf-8',
                                       allow_unicode      = allow_unicode,
                                       indent             = 2,
                                       explicit_start     = True,
                                       default_flow_style = False)

  def save(self, output, human_time = True, close = True, allow_unicode = True):
    """
    Saves the subtitle in native (YAML) format. If 'output' is file object, it will
    be closed if 'close' set to True after save is done.
    """
    if isinstance(output, basestring):
      try:
        output = io.BufferedWriter(io.open(output, 'wb'))
      except IOError:
        # TODO Custom exception
        raise
    if isinstance(output, file):
      output = io.BufferedWriter(io.FileIO(output.fileno()), closefd = close)
    if not isinstance(output, io.BufferedIOBase):
      raise TypeError("Save method accepts filename or file object.")
    # Put a text wrapper around it
    output = io.TextIOWrapper(output, encoding = 'utf-8')

    self.dump(output, human_time = human_time,
                      allow_unicode = allow_unicode)

    if close:
      output.close()
    else:
      output.detach()
