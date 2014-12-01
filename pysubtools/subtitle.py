from __future__ import absolute_import

from .parsers import BaseParser

class SubtitleUnit(object):
  """Class for holding time and text data of a subtitle unit.
  """
  def __init__(self, start, end, text = None):
    self.start = float(start)
    self.end = float(end)

    if text is not None:
      if not isinstance(text, (list, set)):
        text = list(text)

      self.text = []
      for line in text:
        if not isinstance(line, unicode):
          raise TypeError("Subtitle line needs to be unicode instead of '{}'".format(type(line)))
        self.text.append(line)

  def distance(self, other):
    """Calculates signed distance with other subtitle unit.
    """
    if not isinstance(other, SubtitleUnit):
      raise TypeError("Can calculate distance only with SubtitleUnit and not '{}'".format(type(other)))

    return other.start - self.start

  @property
  def duration(self):
    """Returns duration of subtitle unit in seconds.
    """
    return self.end - self.start

  @property
  def length(self):
    """Returns length of the SbtitleUnit (in characters).
    """
    return sum((len(i) for i in self.text))

  def move(self, distance):
    """Moves subtitle unit by 'distance' seconds.
    """
    if not isinstance(distance, (int, long, float)):
      raise TypeError("Need type of int, long or float instead of '{}'".format(type(distance)))
    self.start += distance
    self.end += distance

  def get_moved(self, distance):
    """Same as SubtitleUnit.move, just returns a copy while itself is unchanged.
    """
    clone = SubtitleUnit(self.start, self.end, self.text)
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
    """Same as SubtitleUnit.stretch, just returns a copy while itself is unchanged.
    """
    clone = SubtitleUnit(self.start, self.end, self.text)
    clone.stretch(factor)
    return clone

  def __sub__(self, other):
    """See SubtitleUnit.get_moved.
    """
    if not isinstance(other, (int, long, float)):
      raise TypeError("Need type of int, long or float instead of '{}'".format(type(other)))
    return self.get_moved(-1 * other)

  def __add__(self, other):
    """See SubtitleUnit.get_moved.
    """
    return self.get_moved(other)

  def __isub__(self, other):
    """Same as SubtitleUnit.move
    """
    if not isinstance(other, (int, long, float)):
      raise TypeError("Need type of int, long or float instead of '{}'".format(type(other)))
    self.move(-1 * other)

  def __iadd__(self, other):
    """Same as SubtitleUnit.move
    """
    self.move(other)

  def __mul__(self, other):
    """See SubtitleUnit.get_stretched.
    """
    return self.get_stretched(other)

  def __imul__(self, other):
    """See SubtitleUnit.stretch.
    """
    self.stretch(other)

  def __eq__(self, other):
    if not isinstance(other, SubtitleUnit):
      raise TypeError("Can compare only with other SubtitleUnit, provided with '{}'".format(type(other)))
    return self.text == other.text and self.start == other.start and self.end == other.end

  def __repr__(self):
    return "SubtitleUnit({}, {}, {})".format(self.start, self.end, self.text)

class Subtitle(object):
  """The whole subtitle.

  To load a subtitle, use pysubparsers.load.
  """
  def __init__(self, parser):
    if not isinstance(parser, BaseParser):
      raise TypeError("Need parser not '{}'".format(type(parser)))

    self._units = []
    for unit in parser.parsed:
      start, end = unit['header']['time']
      text = unit['text']
      self.add_unit(SubtitleUnit(start, end, text))
    self.order()

  def add_unit(self, unit, order = True):
    """Adds a new 'unit'.

    Parameters:
      order - If True it will also sort the units. Set False if you plan to add a lot of units.
    """
    if not isinstance(unit, SubtitleUnit):
      raise TypeError("Can add only subtitleUnit, you passed '{}'".format(type(unit)))

    self._units.append(unit)
    if order:
      self.order()

  def order(self):
    """Maintains order of subtitles.
    """
    self._units.sort(key = lambda x: x.start)

  def check_overlaps(self):
    """Checks for overlaps and returns them in list.
    """
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
    """Proxy for internal storage.
    """
    self._units.remove(unit)

  def index(self, unit):
    """Proxy for internal storage.
    """
    return self._units.index(unit)

  def __getitem__(self, index):
    """Proxy for internal storage.
    """
    return self._units[index]

  def __delitem__(self, index):
    """Proxy for internal storage.
    """
    del self._units[index]

  def __len__(self):
    """Proxy for internal storage.
    """
    return len(self._units)

  def __iter__(self):
    """Proxy for internal storage.
    """
    return iter(self._units)

  def __reversed__(self):
    """Proxy for internal storage.
    """
    return reversed(self._units)

  def __eq__(self, other):
    """Proxy for internal storage.
    """
    return self._units == other._units

  def __contains__(self, unit):
    """Proxy for internal storage.
    """
    # TODO make possible to test with string?
    return unit in self._units
