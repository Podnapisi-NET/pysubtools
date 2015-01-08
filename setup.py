# -*- coding: utf8 -*-
from setuptools import setup, find_packages

setup (
  name = "PySubTools",
  version = "0.1-dev",
  packages = find_packages(),
  test_suite = 'tests',

  install_requires = ['chardet',
                      'state-machine',
                      'pyyaml'],

  # metadata for upload to PyPI
  author = "Gregor Kališnik, Unimatrix",
  author_email = "gregor@kalisnik.si, info@unimatrix.si",
  description = "A set of parsers and exports for subtitles in various formats",
  license = "BSD",
  keywords = "parsing exporting subtitles srt",
)
