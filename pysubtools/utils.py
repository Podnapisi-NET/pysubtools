from __future__ import absolute_import

import gzip

class PatchedGzipFile(gzip.GzipFile):
  """
  A patched gzip file to be able to use TextIOWrapper
  around it. Not needed in Python 3.3+
  """
  def read1(self, n):
    return self.read(n)