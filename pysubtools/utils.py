from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import gzip
import sys

class PatchedGzipFile(gzip.GzipFile):
  """
  A patched gzip file to be able to use TextIOWrapper
  around it. Not needed in Python 3.3+
  """
  def read1(self, n):
    return self.read(n)

class UnicodeMixin(object):
  """Mixin class to handle defining the proper __str__/__unicode__
  methods in Python 2 or 3."""

  if sys.version_info[0] >= 3: # Python 3
    def __str__(self):
      return self.__unicode__()
  else:  # Python 2
    def __str__(self):
      return self.__unicode__().encode('utf8')
