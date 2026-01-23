import io
import sys
import typing
import yaml
from .utils import UnicodeMixin


def prepare_reader(f: typing.Union[str, io.BufferedIOBase]) -> io.TextIOWrapper:
    if isinstance(f, str):
        f = io.BufferedReader(io.open(f, "rb"))

    if not isinstance(f, io.BufferedIOBase):
        raise TypeError("Load method accepts filename or file object.")
    return io.TextIOWrapper(f)


class HumanTime(yaml.YAMLObject, UnicodeMixin):
    yaml_loader: typing.Type[yaml.SafeLoader] = yaml.SafeLoader
    yaml_dumper: typing.Type[yaml.SafeDumper] = yaml.SafeDumper

    yaml_tag: str = "!human_time"

    def __init__(self, hours: int = 0, minutes: int = 0, seconds: float = 0.0) -> None:
        self.hours = int(hours)
        self.minutes = int(minutes)
        self.seconds = float(seconds)

    @classmethod
    def from_yaml(cls, loader: yaml.Loader, node: typing.Union[yaml.ScalarNode, yaml.MappingNode]) -> float:
        value = loader.construct_scalar(node)
        return float(cls.from_string(value))

    @classmethod
    def to_yaml(cls, dumper: yaml.Dumper, data: typing.Union[int, float, 'HumanTime']) -> yaml.ScalarNode:
        if isinstance(data, (int, float)):
            data = cls.from_seconds(data)

        return dumper.represent_scalar("!human_time", str(data))

    @classmethod
    def from_seconds(cls, time: float) -> 'HumanTime':
        obj = cls()
        time = float(time)
        obj.hours = int(time // 3600)
        time -= obj.hours * 3600
        obj.minutes = int(time // 60)
        time -= obj.minutes * 60
        obj.seconds = time
        return obj

    @classmethod
    def from_string(cls, time: str) -> 'HumanTime':
        obj = cls()

        if isinstance(time, str):
            time_parts = time.split(":")
            obj.hours = int(time_parts[0])
            obj.minutes = int(time_parts[1])
            obj.seconds = float(time_parts[2])
        else:
            raise TypeError("Unknown time format.")

        return obj

    def __unicode__(self) -> str:
        return "{:02d}:{:02d}:{:06.3f}".format(self.hours, self.minutes, self.seconds)

    def __float__(self) -> float:
        return self.to_seconds()

    def __int__(self) -> int:
        return int(self.to_seconds())

    def to_seconds(self) -> float:
        return self.hours * 3600 + self.minutes * 60 + self.seconds


class Frame(yaml.YAMLObject, UnicodeMixin):
    yaml_loader: typing.Type[yaml.SafeLoader] = yaml.SafeLoader
    yaml_dumper: typing.Type[yaml.SafeDumper] = yaml.SafeDumper

    yaml_tag: str = "!frame"

    def __init__(self, frame: int):
        self._frame = frame

    @classmethod
    def from_yaml(cls, loader: yaml.Loader, node: typing.Union[yaml.ScalarNode, yaml.MappingNode]) -> 'Frame':
        value = loader.construct_scalar(node)
        return cls(int(value))

    @classmethod
    def to_yaml(cls, dumper: yaml.Dumper, data: typing.Union[int, 'Frame']) -> yaml.ScalarNode:
        if isinstance(data, int):
            data = cls(data)

        return dumper.represent_scalar("!frame", str(data._frame))

    def __int__(self):
        raise ValueError("Cannot convert frame to time without specified FPS.")

    def __float__(self):
        raise ValueError("Cannot convert frame to time without specified FPS.")

    def __eq__(self, value: typing.Any) -> bool:
        return self._frame == value

    def __hash__(self) -> int:
        return hash(self._frame)

    def __gt__(self, value: typing.Any) -> bool:
        return self._frame > value

    def __lt__(self, value: typing.Any) -> bool:
        return self._frame < value

    def __repr__(self) -> str:
        return "Frame({})".format(self._frame)


class SubtitleLine(UnicodeMixin):
    """
    Class representing a line inside SubtitleUnit. It acts as an ordinary
    unicode objects, but has an ability to store additional metadata.
    """

    def __init__(self, text: str, **kwargs):
        self.text = text
        # Update with additional metadata
        self.__dict__.update(kwargs)

    def export(self) -> typing.Union[str, typing.Dict[str, typing.Any]]:
        """Returns line in format for export."""
        output = dict(self.__dict__)
        text = output.pop("text", "")
        if not output:
            output = text
        else:
            output["text"] = text
        return output

    @classmethod
    def from_export(cls, obj: typing.Dict[str, typing.Any]) -> 'SubtitleLine':
        return cls(**obj)

    def __unicode__(self) -> str:
        return self.text

    def __repr__(self) -> str:
        return "SubtitleLine({}{})".format(
            self.text,
            (
                (
                    ", "
                    + ", ".join(
                        [" = ".join([k, str(v)]) for k, v in self.meta.items()]
                    )
                )
                if self.meta
                else ""
            ),
        )
    
    def __eq__(self, other: typing.Any) -> bool:
        if not isinstance(other, SubtitleLine):
            return False
        return self.__dict__ == other.__dict__

    def __len__(self) -> int:
        return len(self.text)

    @property
    def meta(self) -> typing.Dict[str, typing.Any]:
        d = dict(self.__dict__)
        # Remove important part of metadata
        d.pop("text")
        return d


class SubtitleLines(typing.List[SubtitleLine]):
    """Modified list class for special tratment of lines."""

    __slots__ = ()

    def __new__(cls, lines: typing.List[SubtitleLine] = []) -> 'SubtitleLines':
        obj = super(SubtitleLines, cls).__new__(cls)
        for line in lines:
            obj.append(line)
        return obj

    @staticmethod
    def _validate(value: typing.Union[str, SubtitleLine]) -> 'SubtitleLine':
        if isinstance(value, str):
            value = SubtitleLine(value)

        if not isinstance(value, SubtitleLine):
            raise TypeError(
                "Subtitle line needs to be unicode instead of '{}'".format(type(value))
            )
        return value

    def append(self, value: typing.Union[str, SubtitleLine]) -> None:
        value = self._validate(value)
        super(SubtitleLines, self).append(value)

    def __setitem__(self, index: typing.Any, value: typing.Any) -> None:
        value = self._validate(value)
        super(SubtitleLines, self).__setattr__(index, value)


class SubtitleUnit:
    """Class for holding time and text data of a subtitle unit."""

    def __init__(self, start: typing.Union[float, Frame], end: typing.Union[float, Frame], lines: typing.Any = None, **meta):
        self.start = float(start) if not isinstance(start, Frame) else start
        self.end = float(end) if not isinstance(end, Frame) else end
        self._lines = SubtitleLines()

        self.__dict__.update(meta)

        if lines is not None:
            if not isinstance(lines, (list, set)):
                lines = list(lines)

            for line in lines:
                self._lines.append(line)

    def distance(self, other: 'SubtitleUnit'):
        """Calculates signed distance with other subtitle unit."""
        if not isinstance(other, SubtitleUnit):
            raise TypeError(
                "Can calculate distance only with SubtitleUnit and not '{}'".format(
                    type(other)
                )
            )

        # TODO: This may not work for Frames?
        return other.start - self.start

    def __iter__(self) -> typing.Iterator[SubtitleLine]:
        return self._lines.__iter__()

    def __setitem__(self, index, value) -> None:
        self._lines[index] = value

    def __getitem__(self, index) -> SubtitleLine:
        return self._lines[index]

    def append(self, value: typing.Union[str, SubtitleLine]) -> None:
        self._lines.append(value)

    @property
    def lines(self) -> typing.Iterator[str]:
        return map(str, self._lines)

    @property
    def duration(self) -> float:
        """Returns duration of subtitle unit in seconds."""
        # TODO: It may not work for Frames?
        return self.end - self.start

    @property
    def length(self) -> int:
        """Returns length of the SubtitleUnit (in characters)."""
        return sum((len(line) for line in self._lines))

    def move(self, distance: typing.Union[int, float]) -> None:
        """Moves subtitle unit by 'distance' seconds."""
        if not isinstance(distance, (int, float)):
            raise TypeError(
                "Need type of int, long or float instead of '{}'".format(type(distance))
            )
        # TODO: Does this really work for Frames?
        self.start += distance
        self.end += distance

    def get_moved(self, distance: typing.Union[int, float]) -> 'SubtitleUnit':
        """Same as SubtitleUnit.move, just returns a copy while itself is unchanged."""
        clone = SubtitleUnit(**self.__dict__)
        clone.move(distance)
        return clone

    def stretch(self, factor: typing.Union[int, float]) -> None:
        """Stretches the unit for 'factor'."""
        if not isinstance(factor, (int, float)):
            raise TypeError(
                "Need type of int, long or float instead of '{}'".format(type(factor))
            )
        # TODO: Does this really work for Frames?
        self.start *= factor
        self.end *= factor

    def get_stretched(self, factor: typing.Union[int, float]) -> 'SubtitleUnit':
        """Same as SubtitleUnit.stretch, just returns a copy while itself is unchanged."""
        clone = SubtitleUnit(**self.__dict__)
        clone.stretch(factor)
        return clone

    @property
    def meta(self) -> typing.Dict[str, typing.Any]:
        d = dict(self.__dict__)
        # Remove important part of metadata and lines
        d.pop("start")
        d.pop("end")
        d.pop("_lines")
        return d

    def __sub__(self, other) -> 'SubtitleUnit':
        """See SubtitleUnit.get_moved."""
        if not isinstance(other, (int, float)):
            raise TypeError(
                "Need type of int, long or float instead of '{}'".format(type(other))
            )
        return self.get_moved(-1 * other)

    def __add__(self, other) -> 'SubtitleUnit':
        """See SubtitleUnit.get_moved."""
        return self.get_moved(other)

    def __isub__(self, other) -> None:
        """Same as SubtitleUnit.move."""
        if not isinstance(other, (int, float)):
            raise TypeError(
                "Need type of int, long or float instead of '{}'".format(type(other))
            )
        self.move(-1 * other)

    def __iadd__(self, other) -> None:
        """Same as SubtitleUnit.move"""
        self.move(other)

    def __mul__(self, other) -> 'SubtitleUnit':
        """See SubtitleUnit.get_stretched."""
        return self.get_stretched(other)

    def __imul__(self, other) -> None:
        """See SubtitleUnit.stretch."""
        self.stretch(other)

    def __eq__(self, other) -> bool:
        if not isinstance(other, SubtitleUnit):
            raise TypeError(
                "Can compare only with other SubtitleUnit, provided with '{}'".format(
                    type(other)
                )
            )

        return self.__dict__ == other.__dict__

    def __len__(self) -> int:
        return len(self._lines)

    def __repr__(self) -> str:
        d = dict(self.__dict__)
        # Get known attributes
        start = d.pop("start")
        end = d.pop("end")
        lines = d.pop("_lines")
        return "SubtitleUnit({}, {}, {}, {})".format(start, end, lines, d)

    def to_dict(self, human_time=True) -> typing.Dict[str, typing.Any]:
        """Returns subtitle unit as a dict (with some human readable things)."""
        output = {}
        output.update(self.__dict__)
        # Overide custom attributes
        output["start"] = (
            HumanTime.from_seconds(self.start)
            if human_time and not isinstance(self.start, Frame)
            else self.start
        )
        output["end"] = (
            HumanTime.from_seconds(self.end)
            if human_time and not isinstance(self.end, Frame)
            else self.end
        )
        # And lines
        output["lines"] = [i.export() for i in self._lines]

        # Remove lines
        output.pop("_lines")
        return output

    @classmethod
    def from_dict(cls, input: typing.Dict[str, typing.Any]) -> 'SubtitleUnit':
        """Creates SubtitleUnit from specified 'input' dict."""
        input = dict(input)
        lines = input.pop("lines", [])
        # TODO: Why do we allow strings instead of only SubtitleLine instances?
        lines = [
            (
                i
                if isinstance(i, str)
                else (
                    i.decode("utf-8")
                    if isinstance(i, bytes)
                    else SubtitleLine.from_export(i)
                )
            )
            for i in lines
        ]

        return cls(lines=SubtitleLines(lines), **input)


class Subtitle:
    """
    The whole subtitle.

    To load a subtitle in non-native format, use parsers.Parser.from_data.
    """

    def __init__(self, units: typing.Iterable[SubtitleUnit] = [], **meta):
        self._units: typing.List[SubtitleUnit] = []
        self.__dict__.update(meta)
        for unit in units:
            self.append(unit)

    def add_unit(self, unit: SubtitleUnit):
        """Adds a new 'unit' and sorts the units. If adding many units, use append instead."""
        self.append(unit)
        self.order()

    def order(self) -> None:
        """Maintains order of subtitles."""
        self._units.sort(key=lambda x: x.start)

    def check_overlaps(self) -> typing.List[typing.Tuple[int, int]]:
        """Checks for overlaps and returns them in list."""
        overlaps: typing.List[typing.Tuple[int, int]] = []
        for current_unit in self._units[:-1]:
            i = self._units.index(current_unit)
            for next_unit in self._units[i + 1 :]:
                if current_unit.end > next_unit.start:
                    overlaps.append((i, self._units.index(next_unit)))
                else:
                    break

        return overlaps

    def remove(self, unit: SubtitleUnit) -> None:
        """Proxy for internal storage."""
        if not isinstance(unit, SubtitleUnit):
            raise TypeError(
                "Can remove only SubtitleUnit, you passed '{}'".format(type(unit))
            )

        self._units.remove(unit)

    def index(self, unit: SubtitleUnit) -> int:
        """Proxy for internal storage."""
        if not isinstance(unit, SubtitleUnit):
            raise TypeError(
                "Can index only SubtitleUnit, you passed '{}'".format(type(unit))
            )

        return self._units.index(unit)

    def insert(self, index: int, unit: SubtitleUnit) -> None:
        """Proxy for internal storage."""
        if not isinstance(unit, SubtitleUnit):
            raise TypeError(
                "Can add only SubtitleUnit, you passed '{}'".format(type(unit))
            )

        return self._units.insert(index, unit)

    def append(self, unit: SubtitleUnit):
        """Proxy for internal storage."""
        if not isinstance(unit, SubtitleUnit):
            raise TypeError(
                "Can add only SubtitleUnit, you passed '{}'".format(type(unit))
            )

        return self._units.append(unit)

    def __getitem__(self, index: int) -> SubtitleUnit:
        """Proxy for internal storage."""
        return self._units[index]

    def __setitem__(self, index: int, unit: SubtitleUnit) -> None:
        """Proxy for internal storage."""
        if not isinstance(unit, SubtitleUnit):
            raise TypeError(
                "Can add only SubtitleUnit, you passed '{}'".format(type(unit))
            )

        self._units[index] = unit

    def __delitem__(self, index: int) -> None:
        """Proxy for internal storage."""
        del self._units[index]

    def __len__(self) -> int:
        """Proxy for internal storage."""
        return len(self._units)

    def __iter__(self) -> typing.Iterator[SubtitleUnit]:
        """Proxy for internal storage."""
        return iter(self._units)

    def __reversed__(self) -> typing.Iterator[SubtitleUnit]:
        """Proxy for internal storage."""
        return reversed(self._units)

    def __eq__(self, other) -> bool:
        """Proxy for internal storage."""
        if self.__dict__ != other.__dict__:
            print(self.__dict__, other.__dict__)
        return self.__dict__ == other.__dict__

    def __contains__(self, unit) -> bool:
        """Proxy for internal storage."""
        # TODO make possible to test with string?
        return unit in self._units

    @property
    def meta(self) -> typing.Dict[str, typing.Any]:
        # Remove non-metadata from dict
        d = dict(self.__dict__)
        d.pop("_units", None)
        return d

    @classmethod
    def from_dict(cls, data: typing.Optional[typing.Dict[str, typing.Any]]) -> 'Subtitle':
        """Creates Subtitle object from dict, parsed from YAML."""
        if data is None:
            data = {}
        data = dict(data)
        data["units"] = [SubtitleUnit.from_dict(i) for i in data.get("units") or []]
        return cls(**data)

    @classmethod
    def from_file(cls, input: typing.Union[str, io.BufferedIOBase]) -> typing.Optional['Subtitle']:
        """
        Loads a subtitle from file in YAML format. If have multiple documents,
        set 'multi' to True. Do note, when multi is set to True, this method
        returns a generator object.
        """
        with prepare_reader(input) as reader:
        # Read
            obj = cls.from_yaml(reader)

        # Done
        if obj:
            return obj

    @classmethod
    def from_file_multi(cls, input: typing.Union[str, io.BufferedIOBase]) -> typing.Generator['Subtitle', typing.Any, None]:
        """Loads multiple subtitles from file 'input'. It returns a generator object."""
        reader = prepare_reader(input)

        for i in cls.from_multi_yaml(reader):
            # Needed to prevent input from closing
            yield i

        # Detach wrapper
        reader.detach()

        # Done

    @classmethod
    def from_yaml(cls, input: typing.Any) -> 'Subtitle':
        """Loads a subtitle from YAML format, uses safe loader."""
        # Construct a python dict
        data = yaml.safe_load(input)

        # Return our subtitle
        return cls.from_dict(data)

    @classmethod
    def from_multi_yaml(cls, input: typing.Any) -> typing.Generator['Subtitle', typing.Any, None]:
        """Loads multiple subtitles from YAML format, uses safe loader."""
        for data in yaml.safe_load_all(input):
            yield cls.from_dict(data)

    def dump(self, output: typing.Any = None, human_time: bool = True, allow_unicode: bool = True) -> bytes:
        """Dumps this subtitle in YAML format with safe dumper."""
        # Construct a python dict
        obj = dict(self.__dict__)
        obj["units"] = [i.to_dict(human_time) for i in obj.pop("_units")]
        # Dump it
        return yaml.safe_dump(
            obj,
            output,
            encoding="utf-8",
            allow_unicode=allow_unicode,
            indent=2,
            explicit_start=True,
            default_flow_style=False,
        )

    def save(self, output: typing.Union[str, io.BufferedIOBase], human_time: bool = True, close: bool = True, allow_unicode: bool = True) -> None:
        """
        Saves the subtitle in native (YAML) format. If 'output' is file object, it will
        be closed if 'close' set to True after save is done.
        """
        if isinstance(output, str):
            try:
                output = io.BufferedWriter(io.open(output, "wb"))
            except IOError:
                # TODO Custom exception
                raise

        if not isinstance(output, io.BufferedIOBase):
            raise TypeError("Save method accepts filename or file object.")
        # Put a text wrapper around it
        text_output = io.TextIOWrapper(output, encoding="utf-8")

        self.dump(text_output, human_time=human_time, allow_unicode=allow_unicode)

        if close:
            text_output.close()
        else:
            text_output.detach()
