from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from .base import Exporter

from ..subtitle import HumanTime

class SubRipExporter(Exporter):
  """Exported for SubRip format."""
  FORMAT = 'SubRip'

  def _init(self, encoding = 'utf-8', line_ending = b'\n'):
    self._encoding = encoding
    self._line_ending = line_ending

  @staticmethod
  def _convert_time(time):
    output = []

    if isinstance(time, (float, int)):
      time = HumanTime.from_seconds(time)
    elif not isinstance(time, HumanTime):
      raise TypeError("Expecting time")

    output.append('{:02d}'.format(time.hours))
    output.append('{:02d}'.format(time.minutes))
    seconds = int(time.seconds)
    miliseconds = int((time.seconds - seconds) * 1000)
    output.append('{:02d},{:03d}'.format(seconds, miliseconds))

    return ':'.join(output)

  def _export_metadata(self, metadata):
    # No subtitle wide metadata, just reset counter
    self._unit = 0
    return b''

  def _export_unit(self, unit):
    output = []

    if self._unit:
      # An empty line at the beginning
      output.append(b'')
    self._unit += 1

    # Sequence
    output.append(str(self._unit).encode(self._encoding))
    # Timing
    # TODO 3D positions
    output.append("{} --> {}".format(self._convert_time(unit.start),
                                     self._convert_time(unit.end)).encode(self._encoding))
    # Text
    output.append(self._line_ending.join([i.encode(self._encoding, 'ignore') for i in unit.lines]))

    # End of line
    output.append(b'')

    # All done
    return self._line_ending.join(output)

  def _export_end(self, metadata):
    # No specific footer also
    return b''
