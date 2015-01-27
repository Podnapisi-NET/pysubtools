from __future__ import absolute_import

import unittest
import os
import tempfile
import io
import yaml

from pysubtools import Subtitle, SubtitleUnit
from pysubtools.parsers import Parser
from pysubtools.exporters import Exporter
from pysubtools.utils import PatchedGzipFile as GzipFile

class TestCase(unittest.TestCase):
  def test_sif(self):
    """Test 'Subtitle Intermediate Format' loaders and dumpers."""
    # Make a test subtitle with two lines
    subtitle = Subtitle()
    subtitle.add_unit(SubtitleUnit(
      start = 15,
      end   = 30,
      lines = [u'First line with \u0161']
    ))
    subtitle.add_unit(SubtitleUnit(
      start = 65,
      end   = 89,
      lines = [u'Another, but a two liner \u010d',
               u'Yes, I  said two liner! \u017e']
    ))

    # Write it
    tmpfd, tmp = tempfile.mkstemp()
    tmpfd2, tmp2 = tempfile.mkstemp()
    subtitle.save(io.BufferedWriter(io.FileIO(tmpfd, mode = 'w')))
    subtitle.save(io.BufferedWriter(io.FileIO(tmpfd2, mode = 'w')), human_time = False)

    # Load it and test
    assert Subtitle.from_file(tmp) == subtitle
    assert Subtitle.from_file(tmp2) == subtitle

    # Remove temp files
    os.unlink(tmp)
    os.unlink(tmp2)

  def test_sif_gz(self):
    """Test gzipped 'Subtitle Intermediate Format' loaders and dumpers (just wrapped around GzipFile)."""
    # Make a test subtitle with two lines
    subtitle = Subtitle()
    subtitle.add_unit(SubtitleUnit(
      start = 15,
      end   = 30,
      lines = [u'First line with \u0161']
    ))
    subtitle.add_unit(SubtitleUnit(
      start = 65,
      end   = 89,
      lines = [u'Another, but a two liner \u010d',
               u'Yes, I  said two liner! \u017e']
    ))

    # Write it
    tmpfd, tmp = tempfile.mkstemp()
    tmpfd2, tmp2 = tempfile.mkstemp()
    subtitle.save(GzipFile(tmp, mode = 'wb'))
    subtitle.save(GzipFile(tmp2, mode = 'wb'), human_time = False)

    # Load it and test
    assert Subtitle.from_file(GzipFile(tmp, mode = 'rb')) == subtitle
    assert Subtitle.from_file(GzipFile(tmp2, mode = 'rb')) == subtitle

    # Remove temp files
    os.unlink(tmp)
    os.unlink(tmp2)

  def test_multi_sif_gz(self):
    """Test multiple gzipped subtitles."""
    # Make a test subtitle with two lines
    subtitle = Subtitle()
    subtitle.add_unit(SubtitleUnit(
      start = 15,
      end   = 30,
      lines = [u'First line with \u0161']
    ))
    subtitle.add_unit(SubtitleUnit(
      start = 65,
      end   = 89,
      lines = [u'Another, but a two liner \u010d',
               u'Yes, I  said two liner! \u017e']
    ))
    subtitle2 = Subtitle()
    subtitle2.add_unit(SubtitleUnit(
      start = 16,
      end   = 31,
      lines = [u'First line with \u0161']
    ))
    subtitle2.add_unit(SubtitleUnit(
      start = 66,
      end   = 90,
      lines = [u'Another, but a two liner \u010d',
               u'Yes, I  said two liner! \u017e']
    ))
    subtitle3 = Subtitle()
    subtitle3.add_unit(SubtitleUnit(
      start = 17,
      end   = 32,
      lines = [u'First line with \u0161']
    ))
    subtitle3.add_unit(SubtitleUnit(
      start = 67,
      end   = 91,
      lines = [u'Another, but a two liner \u010d',
               u'Yes, I  said two liner! \u017e']
    ))

    # Write it (several times)
    tmpfd, tmp = tempfile.mkstemp()
    tmpf = GzipFile(tmp, mode = 'wb')
    subtitle.save(tmpf, close = False)
    subtitle2.save(tmpf, close = False)
    subtitle3.save(tmpf)

    # Load it and test
    tmpf = GzipFile(tmp, mode = 'rb')
    assert Subtitle.from_file(tmpf, multi = True) == [subtitle,
                                                      subtitle2,
                                                      subtitle3]

    # Remove temp files
    os.unlink(tmp)

  def test_subrip(self):
    """Test SubRip parser."""
    # Go through all subtitles
    root = './tests/data/srt'
    for filename in (i for i in os.listdir(root) if i.endswith('.srt')):
      with open(os.path.join(root, filename), 'rb') as f:
        parser = Parser.from_format('SubRip')
        parsed = parser.parse(f)

        result = os.path.join(root, filename[:-4])
        if os.path.isfile(result + '.msgs.yaml'):
          (encoding, warnings) = yaml.load(open(result + '.msgs.yaml', 'r'))
          sub = Subtitle.from_file(result + '.sif')
        else:
          # Write it
          yaml.dump((parser.encoding, parser.warnings), open(result + '.msgs.yaml', 'w'),
                    default_flow_style = False)
          parsed.save(result + '.sif', allow_unicode = False)
          continue

        assert parser.encoding == encoding
        assert parser.warnings == warnings
        assert sub == parsed

  def test_subrip_export(self):
    """Tests SubRip exporter on a simple subtitle."""
    subtitle = Subtitle()
    subtitle.add_unit(SubtitleUnit(
      start = 15,
      end   = 30,
      lines = [u'First line with \u0161']
    ))
    subtitle.add_unit(SubtitleUnit(
      start = 65,
      end   = 89,
      lines = [u'Another, but a two liner \u010d',
               u'Yes, I  said two liner! \u017e']
    ))
    subtitle.add_unit(SubtitleUnit(
      start = 3665,
      end   = 3689,
      lines = [u'Another, but a two liner \u010d',
               u'Yes, I  said two liner! \u017e']
    ))

    # Construct exporter
    exporter = Exporter.from_format('SubRip')

    # Export
    buf = io.BytesIO()
    exporter.export(buf, subtitle)

    # Now, check the outputted subtitle
    assert buf.getvalue() == """1
00:00:15,000 --> 00:00:30,000
First line with \xc5\xa1

2
00:01:05,000 --> 00:01:29,000
Another, but a two liner \xc4\x8d
Yes, I  said two liner! \xc5\xbe

3
01:01:05,000 --> 01:01:29,000
Another, but a two liner \xc4\x8d
Yes, I  said two liner! \xc5\xbe
"""

    # Now we try with different encoding
    buf = io.BytesIO()
    exporter = Exporter.from_format('SubRip', encoding = 'cp1250')
    exporter.export(buf, subtitle)

    assert buf.getvalue() == """1
00:00:15,000 --> 00:00:30,000
First line with \x9a

2
00:01:05,000 --> 00:01:29,000
Another, but a two liner \xe8
Yes, I  said two liner! \x9e

3
01:01:05,000 --> 01:01:29,000
Another, but a two liner \xe8
Yes, I  said two liner! \x9e
"""
