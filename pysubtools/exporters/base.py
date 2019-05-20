from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io

from ..subtitle import Subtitle


class NoExporterFound(Exception):
    pass


class Exporter(object):
    """Base class for exporting Subtitle."""

    @staticmethod
    def from_format(format, **options):
        """Returns an exporter for specified 'format'."""
        for exporter in Exporter.__subclasses__():
            if exporter.FORMAT == format:
                return exporter(**options)
        raise NoExporterFound(
            "Could not find exporter with name '{}'.".format(format))

    def __init__(self, **options):
        self._init(**options)

    def _init(self, **options):
        """A conveniance init method (no need for overloading)."""
        pass

    def _export_metadata(self, metadata):
        """
        Returns subtitles metadata in format. In your implementation,
        make sure you output str object. Parameter 'metadata' is in
        dict object.
        """
        raise NotImplementedError

    def _export_unit(self, unit):
        """
        Returns whole subtitle unit in format. In your implementation,
        make sure you output str object.
        """
        raise NotImplementedError

    def _export_end(self, metadata):
        """Returns the end part of subtitle."""
        raise NotImplementedError

    @property
    def format(self):
        return self.FORMAT

    def export(self, output, subtitle):
        """Exports to 'output', it may be filename or a file object."""
        if not isinstance(subtitle, Subtitle):
            raise TypeError("Can export only Subtitle objects.")

        try:
            basestring
        except NameError:
            # Python3 compat
            basestring = str

        if isinstance(output, basestring):
            output = io.BufferedWriter(io.open(output, 'wb'))

        try:
            if isinstance(output, file):
                output = io.BufferedWriter(
                    io.FileIO(output.fileno(), closefd=False,
                              mode=output.mode))
        except NameError:
            # Python3 does not need this
            pass

        if not isinstance(output, io.BufferedIOBase):
            raise TypeError(
                """Output needs to be a filename, file or BufferedIOBase with
                write capability.""")

        # Export subtitle metadata
        output.write(self._export_metadata(subtitle.meta))

        # Go through units and export one by one
        for unit in subtitle:
            output.write(self._export_unit(unit))

        # The final piece
        output.write(self._export_end(subtitle.meta))

        # Done
