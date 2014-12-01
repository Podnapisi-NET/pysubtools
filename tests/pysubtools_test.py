from __future__ import absolute_import

import unittest
import os
import os.path
import pickle

from pysubtools import load, Subtitle

class TestCase(unittest.TestCase):
  def test_subrip(self):
    """Test SubRip parser.
    """
    # Go through all subtitles
    root = './tests/data/srt'
    for filename in (i for i in os.listdir(root) if i.endswith('.srt')):
      with open(os.path.join(root, filename), 'r') as f:
        parser = load(f, format = 'SubRip')
        (encoding, warnings, sub) = pickle.load(open(os.path.join(root, filename + '.pickle'), 'r'))
        assert parser.encoding == encoding
        assert parser.warnings == warnings
        assert sub == Subtitle(parser)
