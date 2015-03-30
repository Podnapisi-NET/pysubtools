from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest
import os
import tempfile
import io
import yaml

from pysubtools import Subtitle, SubtitleUnit
from pysubtools.parsers import Parser, encodings
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
      lines = ['First line with \u0161']
    ))
    subtitle.add_unit(SubtitleUnit(
      start    = 65,
      end      = 89,
      position = {
        'x': 50,
        'y': 30,
      },
      lines = ['Another, but a two liner \u010d',
               'Yes, I  said two liner! \u017e']
    ))
    subtitle[0][0].special = True
    subtitle[0][0].complex = {
      'a': {'4': 2},
      'b': [1,2,3]
    }
    subtitle[1][1].test = 'test'

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

    # And some minor things
    # repr - just checking for exceptions
    repr(subtitle)
    for u in subtitle:
      repr(u)
      for l in u:
        repr(l)

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
      lines = ['First line with \u0161']
    ))
    subtitle.add_unit(SubtitleUnit(
      start = 65,
      end   = 89,
      lines = ['Another, but a two liner \u010d',
               'Yes, I  said two liner! \u017e']
    ))
    subtitle2 = Subtitle()
    subtitle2.add_unit(SubtitleUnit(
      start = 16,
      end   = 31,
      lines = ['First line with \u0161']
    ))
    subtitle2.add_unit(SubtitleUnit(
      start = 66,
      end   = 90,
      lines = ['Another, but a two liner \u010d',
               'Yes, I  said two liner! \u017e']
    ))
    subtitle3 = Subtitle()
    subtitle3.add_unit(SubtitleUnit(
      start = 17,
      end   = 32,
      lines = ['First line with \u0161']
    ))
    subtitle3.add_unit(SubtitleUnit(
      start = 67,
      end   = 91,
      lines = ['Another, but a two liner \u010d',
               'Yes, I  said two liner! \u017e']
    ))

    # Write it (several times)
    tmpfd, tmp = tempfile.mkstemp()
    tmpf = GzipFile(tmp, mode = 'wb')
    subtitle.save(tmpf, close = False)
    subtitle2.save(tmpf, close = False)
    subtitle3.save(tmpf)

    # Load it and test
    tmpf = GzipFile(tmp, mode = 'rb')
    assert list(Subtitle.from_file_multi(tmpf)) == [subtitle,
                                                    subtitle2,
                                                    subtitle3]
    tmpf.close()

    # Remove temp files
    os.unlink(tmp)

  def test_parsers(self):
    """Test parsers."""
    def format_test(root, suffix, format):
      for filename in (i for i in os.listdir(root) if i.endswith(suffix)):
        with open(os.path.join(root, filename), 'rb') as f:
          parser = Parser.from_format(format, stop_level = None)
          parsed = parser.parse(f)

          d = dict(
            encoding = parser.encoding,
            warnings = parser.warnings,
            errors   = parser.errors
          )

          result = os.path.join(root, filename[:-4])
          if os.path.isfile(result + '.msgs.yaml'):
            loaded_d = yaml.load(open(result + '.msgs.yaml', 'r'))
            sub = Subtitle.from_file(result + '.sif')
          else:
            # Write it
            yaml.dump(d, open(result + '.msgs.yaml', 'w'),
                      default_flow_style = False)
            parsed.save(result + '.sif', allow_unicode = False)
            continue

          assert d == loaded_d
          assert sub == parsed

    # Go through all subrips
    format_test('./tests/data/srt', '.srt', 'SubRip')
    format_test('./tests/data/microdvd', '.sub', 'MicroDVD')

  def test_encoding(self):
    """Tests if internal encoder tester works as it should (premature IO closures are the concern)"""
    f = open('./tests/data/corner/encoding_detection.srt', 'rb')

    # Test all possible paths
    parser = Parser.from_format('SubRip')

    # As fileobj
    sub1 = parser.parse(f)

    # As from_data with fileobj
    f.seek(0)
    parser = parser.from_data(f)
    sub3 = parser.parse()

    # As string
    f.seek(0)
    d = f.read()
    sub2 = parser.parse(d)

    # As from_data with string
    parser = parser.from_data(d)
    sub4 = parser.parse()

    # All of them must be the same
    assert sub1 == sub2 == sub3 == sub4

    f = open('./tests/data/corner/encoding_error.srt', 'rb')
    try:
      sub = parser.parse(f)
    except encodings.EncodingError as e:
      assert e.tried_encodings == []

  def test_subrip_export(self):
    """Tests SubRip exporter on a simple subtitle."""
    subtitle = Subtitle()
    subtitle.add_unit(SubtitleUnit(
      start = 15,
      end   = 30,
      lines = ['First line with \u0161']
    ))
    subtitle.add_unit(SubtitleUnit(
      start = 65,
      end   = 89,
      lines = ['Another, but a two liner \u010d',
               'Yes, I  said two liner! \u017e']
    ))
    subtitle.add_unit(SubtitleUnit(
      start = 3665,
      end   = 3689,
      lines = ['Another, but a two liner \u010d',
               'Yes, I  said two liner! \u017e']
    ))

    # Construct exporter
    exporter = Exporter.from_format('SubRip')

    # Export
    buf = io.BytesIO()
    exporter.export(buf, subtitle)

    # Now, check the outputted subtitle
    assert buf.getvalue() == b"""1
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

    assert buf.getvalue() == b"""1
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

  def test_subtitle_lines(self):
    """Tests API of the subtitle lines."""
    sub = Subtitle()
    sub.append(SubtitleUnit(
      0, 1, ['First line', 'Second line']
    ))

    # Check line access
    assert str(sub[0][0]) == 'First line'
    assert str(sub[0][1]) == 'Second line'

    # Add some metadata
    sub[0][0].styles = {
      'color': 'red'
    }
    sub[0][1].styles = {
      'color': 'blue'
    }

    # Check them up
    assert sub[0][0].styles == {
      'color': 'red'
    }
    assert sub[0][1].styles == {
      'color': 'blue'
    }

    # Update lines
    sub[0][0].text = 'Just a line'
    sub[0][1].text = 'Just another line'

    assert str(sub[0][0]) == 'Just a line'
    assert str(sub[0][1]) == 'Just another line'

    # Metadata should still be there
    assert sub[0][0].styles == {
      'color': 'red'
    }
    assert sub[0][1].styles == {
      'color': 'blue'
    }

  def test_lookup(self):
    """Some encoding python cannot read, we need to make sure it won't make a low-level error."""
    f = open('./tests/data/corner/lookup_error.srt', 'rb')
    parser = Parser.from_format('SubRip')

    # This should work now (also, this subtitle has some special chars that without EUC-TW => BIG5-TW would not work)
    sub = parser.parse(f, encoding = 'bullshit')
