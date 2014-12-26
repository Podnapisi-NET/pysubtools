from __future__ import absolute_import

import unittest
import os
import os.path
import pickle

from pysubtools.parsers import Parser

class TestCase(unittest.TestCase):
  def test_subrip(self):
    """Test SubRip parser.
    """
    # Go through all subtitles
    root = './tests/data/srt'
    for filename in (i for i in os.listdir(root) if i.endswith('.srt')):
      with open(os.path.join(root, filename), 'rb') as f:
        parser = Parser.from_format('SubRip')
        (encoding, warnings, sub) = pickle.load(open(os.path.join(root, filename + '.pickle'), 'r'))
        parsed = parser.parse(f)
        assert parser.encoding == encoding
        assert parser.warnings == warnings
        assert sub == parsed

        # Write test cases, use when fixing
        #pickle.dump((parser.encoding, parser.warnings, parsed), open(os.path.join(root, filename + '.pickle'), 'w'))
