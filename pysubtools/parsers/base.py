import io
import typing

from . import encodings


class NoParserError(Exception):
    pass


class ParseError(Exception):
    def __init__(self, line_number: int, column: int, line: str, description: str):
        self.line_number = line_number
        self.column = column
        self.line = line
        self.description = description
        super(ParseError, self).__init__(self.description)

    def __str__(self) -> str:
        return str(self)

    def __unicode__(self) -> str:
        return "Parse error on line {} at column {} error occurred '{}'".format(
            self.line_number, self.column, self.description
        )


class ParseWarning(ParseError):
    def __unicode__(self) -> str:
        return "Parse warning on line {} at column {} warning occurred '{}'".format(
            self.line_number, self.column, self.description
        )


class ParserErrorMessage(typing.TypedDict):
    line_number: int
    col: int
    line: str
    description: str


class Parser(object):
    """Abstract class for all parsers."""

    LEVELS = ("warning", "error")
    FORMAT: str = ""
    _subtitle: typing.Optional[typing.Any] = None
    _stop_level: str = "error"
    parsed = None
    encoding: typing.Optional[str] = None
    encoding_confidence = None

    def __init__(self, stop_level: str = "error"):
        self.warnings: typing.List[ParserErrorMessage] = []
        self.errors: typing.List[ParserErrorMessage] = []
        self._data = None
        self._stop_level: str = stop_level

        # Part of the parser internals
        self._read_lines: typing.List[typing.Union[str, bytes]] = []
        self._current_line_num: int = -1
        self._current_line: typing.Optional[typing.Union[str, bytes]] = None

    def _add_msg(self, level: str, line_number: int, column: int, line: str, description: str):
        if self._stop_level and self.LEVELS.index(level) >= self.LEVELS.index(
            self._stop_level
        ):
            if level == "warning":
                raise ParseWarning(line_number, column, line, description)
            elif level == "error":
                raise ParseError(line_number, column, line, description)

        line = str(line)
        description = str(description)

        msg: ParserErrorMessage = {
            "line_number": int(line_number),
            "col": int(column),
            "line": line,
            "description": description,
        }

        if level == "warning":
            self.warnings.append(msg)
        elif level == "error":
            self.errors.append(msg)

    def add_warning(self, *args, **kwargs):
        self._add_msg("warning", *args, **kwargs)

    def add_error(self, *args, **kwargs):
        self._add_msg("error", *args, **kwargs)

    @staticmethod
    def _normalize_data(data: typing.Union[bytes, io.BytesIO, io.BufferedReader]) -> typing.Union[io.BytesIO, io.BufferedReader]:
        if isinstance(data, bytes):
            data = io.BytesIO(data)
        elif not isinstance(data, (io.BytesIO, io.BufferedReader)):
            raise TypeError("Needs to be a file object or bytes.")
        data.seek(0)
        return data

    @classmethod
    def can_parse(cls, data: typing.Union[bytes, io.BytesIO, io.BufferedReader]) -> bool:
        data = cls._normalize_data(data)
        return cls._can_parse(data)

    @classmethod
    def _can_parse(cls, data: typing.Union[bytes, io.BytesIO, io.BufferedReader]) -> bool:
        """Needs to be reimplemented to quickly check if file seems the proper format."""
        raise NotImplementedError

    def _parse(self) -> typing.Iterable[typing.Any]:
        """
        Parses the file, it returns a list of units in specified format. Needs to be
        implemented by the parser. It can also be a generator (yield)
        """
        raise NotImplementedError

    def _parse_metadata(self) -> typing.Dict[str, typing.Any]:
        """Parses the subtitle metadata (if format has a header at all)."""
        return {}

    def parse(self, data: typing.Optional[typing.Union[io.BytesIO, io.BufferedReader]] = None, encoding: typing.Optional[str] = None, language: typing.Optional[str] = None, **kwargs) -> typing.Any:
        """Parses the file and returns the subtitle. Check warnings after the parse."""
        if data:
            # We have new data, discard old and set up for new
            if self._data is not None:
                try:
                    self._data.detach()
                except Exception:
                    pass
            self._data = self._normalize_data(data)
            # Check encoding
            self.encoding, self.encoding_confidence = encodings.detect(
                self._data, encoding=encoding, language=language
            )
            self._data.seek(0)
            # Wrap it
            self._data = io.TextIOWrapper(
                self._data, self.encoding, newline="", errors="replace"
            )

        from .. import Subtitle, SubtitleUnit
        
        sub = Subtitle(**self._parse_metadata())
        for unit in self._parse(**kwargs):
            try:
                sub.append(SubtitleUnit(**unit["data"]))
            except TypeError:
                # We may have malformed units
                self.add_error(
                    self._current_line_num + 1,
                    1,
                    self._current_line,
                    "Wrongly parsed unit, might be a result of a previous error.",
                )
        return sub

    @staticmethod
    def from_data(data: typing.Union[bytes, io.BytesIO, io.BufferedReader], encoding: typing.Optional[str] = None, language: typing.Optional[str] = None, **kwargs) -> 'Parser':
        """Returns a parser that can parse 'data' in raw string."""
        data = Parser._normalize_data(data)
        encoding, encoding_confidence = encodings.detect(data, encoding, language)
        data.seek(0)

        for parser in Parser.__subclasses__():
            if not parser.can_parse(data):
                continue
            parser = parser(**kwargs)
            parser._data = io.TextIOWrapper(
                data, encoding, newline="", errors="replace"
            )
            parser.encoding = encoding
            parser.encoding_confidence = encoding_confidence
            return parser
        raise NoParserError("Could not find parser.")

    @staticmethod
    def from_format(format: str, **kwargs) -> 'Parser':
        """Returns a parser with 'name'."""
        for parser in Parser.__subclasses__():
            if parser.FORMAT == format:
                return parser(**kwargs)
        raise NoParserError("Could not find parser.")

    def __del__(self):
        # Detach _data
        if self._data:
            try:
                self._data.detach()
            except ValueError:
                # We may have an already closed underlying file object
                pass

    # Iteration methods
    def _next_line(self) -> bool:
        line = self._data.readline() if self._data else None
        if not line:
            return False
        self._current_line_num += 1

        self._current_line = line.rstrip()
        self._read_lines.append(line)

        return True

    def _fetch_line(self, line: int) -> typing.Union[str, bytes]:
        if line > self._current_line_num:
            raise ValueError("Cannot seek forward.")

        return self._read_lines[line].rstrip()

    def _rewind(self) -> None:
        self._current_line_num = -1
        self._read_lines = []
        self._current_line = None
        if self._data:
            self._data.seek(0)
