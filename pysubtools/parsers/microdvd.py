import re

from .base import Parser
from ..subtitle import Frame, SubtitleLine


def update_dict(d, s):
    """Update with recursion."""
    for key in s.keys():
        if isinstance(d.get(key), dict) and isinstance(s[key], dict):
            update_dict(d[key], s[key])
        else:
            d[key] = s[key]


class MicroDVDParser(Parser):
    """Parser for SubRip."""

    FORMAT = "MicroDVD"
    FORMAT_RE = re.compile(
        r"^\{(?P<start>\d+)\}\{(?P<end>\d+)\}(?P<header>(:?\{[^}]+\})*)(?P<text>.*)$",
        re.M,
    )
    HEADER_RE = re.compile(r"^\{DEFAULT\}(?P<header>(:?\{[^}]+\})*)$")

    @classmethod
    def _can_parse(cls, data):
        # Go through first few lines
        can = False
        for i in range(0, 10):
            line = data.readline()
            if isinstance(line, bytes):
                line = line.decode(errors="replace")
            can = bool(cls.FORMAT_RE.search(line))
            if can:
                break
        data.seek(0)
        return can

    def _parse_header(self, header, global_only=False):
        # TODO Add FPS heuristic (first line as fps)
        output = {"local": {}}
        #################################################################
        # Supported header tags (lowercase represent global and local): #
        #  * y - font-style                                             #
        #    * i - italics                                              #
        #    * b - bold                                                 #
        #    * u - underlined                                           #
        #    * s - stroked                                              #
        #  * f - font-family                                            #
        #  * s - font-size                                              #
        #  * c - color ($BBGGRR) -> #RRGGBB                             #
        #  * P - position x,y -> {'x': x, 'y': y}                       #
        #  * H - charset - unused (we've already set it)                #
        #################################################################
        if header is None:
            header = ""
        # Break the header into several ones
        for h in header.replace("{", "").split("}")[:-1]:
            k, v = h.split(":")
            if global_only and k.islower():
                continue
            k = k.strip()
            v = v.strip()
            t = {"styles": {"*": {"text-decoration": []}}}

            if k.lower() == "y":
                # Font style
                for i in v.split(","):
                    i = i.strip()
                    if i == "b":
                        t["styles"]["*"]["font-weight"] = "bold"
                    elif i == "i":
                        t["styles"]["*"]["text-style"] = "italic"
                    elif i == "u":
                        t["styles"]["*"]["text-decoration"].append("underline")
                    elif i == "s":
                        t["styles"]["*"]["text-decoration"].append("line-through")
                    else:
                        self.add_warning(
                            self._current_line_num + 1,
                            1,
                            self._fetch_line(self._current_line_num),
                            "Unknown style tag {}.".format(i),
                        )
                t["styles"]["*"]["text-decoration"] = " ".join(
                    t["styles"]["*"]["text-decoration"]
                )
            elif k.lower() == "f":
                # Font family
                t["styles"]["*"]["font-family"] = v.strip()
            elif k.lower() == "s":
                # Font size
                t["styles"]["*"]["font-size"] = v.strip() + (
                    "px" if v.strip().isdigit() else ""
                )
            elif k.lower() == "c":
                # Text color
                v = v.strip()
                if re.match("^\$[0-9a-fA-F]{6}$", v):
                    t["styles"]["*"]["color"] = "#" + v[5:] + v[3:5] + v[1:3]
                else:
                    self.add_warning(
                        self._current_line_num + 1,
                        1,
                        self._fetch_line(self._current_line_num),
                        "Wrong color format {}.".format(v),
                    )
            elif k == "P":
                # Position
                m = re.match(r"^\s*(\d+)\s*,\s*(\d+)\s*$", v)
                if not m:
                    self.add_warning(
                        self._current_line_num + 1,
                        1,
                        self._fetch_line(self._current_line_num),
                        "Malformed position {}.".format(v),
                    )
                else:
                    t["position"] = {"x": int(m.group(1)), "y": int(m.group(2))}
            elif k == "H":
                # Silently ignore since it is charset setting
                pass
            else:
                self.add_warning(
                    self._current_line_num + 1,
                    1,
                    self._fetch_line(self._current_line_num),
                    "Unknwon header {}.".format(k),
                )

            if not t["styles"]["*"]["text-decoration"]:
                del t["styles"]["*"]["text-decoration"]

            if k.islower():
                update_dict(output["local"], t)
            else:
                update_dict(output, t)

        if global_only:
            del output["local"]

        return output

    def _to_header_dict(self, h):
        if not h:
            return {}

        try:
            h = h[1:-1]
            # Take pair out, and strip them
            d = dict([(j.strip() for j in i.split(":")) for i in h.split("}{")])
            # Take only local ones
            return {(k, v) for k, v in d.items() if k.islower()}
        except ValueError:
            # Cannot parse this header, probably it is wrong
            line = self._fetch_line(self._current_line_num)
            self.add_warning(
                self._current_line_num + 1,
                line.index(h),
                line,
                "It looks like a line header but it's not.",
            )
            return {}

    def _from_header_dict(self, h):
        if not h:
            return ""
        return "{" + "}{".join([":".join([k, v]) for k, v in h.items()]) + "}"

    def _parse_metadata(self):
        # Need for default header lines
        self._skip_lines = set([])

        output = {}
        # Scan the whole subtitle for global metadata
        while self._next_line():
            m = self.HEADER_RE.match(self._current_line.strip())
            if m:
                output.update(self._parse_header(m.group("header"), global_only=True))
                self._skip_lines.add(self._current_line_num)
        # Rewind
        self._rewind()
        return output

    def _parse(self, fps=None, **kwargs):
        while self._next_line():
            if self._current_line_num in self._skip_lines:
                # We have a metadata line
                continue

            m = self.FORMAT_RE.match(self._current_line.strip())
            if not m:
                self.add_error(
                    self._current_line_num + 1,
                    1,
                    self._current_line,
                    "Could not parse line",
                )
            else:
                if not m.group("text"):
                    self.add_warning(
                        self._current_line_num + 1,
                        1,
                        self._fetch_line(self._current_line_num),
                        "Empty unit.",
                    )

                start, end = int(m.group("start")), int(m.group("end"))
                if fps:
                    start /= fps
                    end /= fps
                else:
                    start, end = Frame(start), Frame(end)
                # Parse main header
                header = self._parse_header(m.groupdict().get("header", ""))
                h_inherit = [self._to_header_dict(m.groupdict().get("header", ""))]
                # Go through lines and parse out headers
                lines = []
                for line in m.group("text").split("|"):
                    if line.startswith("{"):
                        h_i = line.index("}") + 1
                        # We have a local header
                        h = self._to_header_dict(line[:h_i])
                    else:
                        h_i = 0
                        h = {}
                    h_inherit.append(h)
                    # Construct local header
                    h = {}
                    for i in h_inherit:
                        h.update(i)
                    h = self._parse_header(self._from_header_dict(h))["local"]

                    # Construct line
                    lines.append(SubtitleLine(line[h_i:], **h))
                # Parse unit
                data = {
                    "start": start,
                    "end": end,
                    "lines": lines,
                }
                # Add unit metadata
                header.pop("local")
                data.update(header)
                # Pass along the unit data
                yield {"data": data}
