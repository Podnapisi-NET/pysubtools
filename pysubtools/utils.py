import gzip


class PatchedGzipFile(gzip.GzipFile):
    """
    A patched gzip file to be able to use TextIOWrapper
    around it. Not needed in Python 3.3+
    """

    def read1(self, size: int = -1) -> bytes:
        return self.read(size)


class UnicodeMixin(object):
    """Mixin class to handle defining the proper __str__/__unicode__
    methods in Python 2 or 3."""

    def __str__(self):
        return self.__unicode__()
