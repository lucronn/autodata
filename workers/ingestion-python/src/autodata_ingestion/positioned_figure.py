"""Read Banktwo's positioned diagram labels as text and bounded coordinates."""

from dataclasses import dataclass, field
from html.parser import HTMLParser
import math
import re


FIGURE_LABEL_LAYOUT = "html-positioned-figure-labels-v1"
_PIXELS = re.compile(r"([0-9]{1,5}(?:\.[0-9]{1,8})?)(px|pt)")
_OVERLAID_MARKER = re.compile("overlayedimage", re.I)
_MAX_LABELS = 32
_MAX_LINES = 8
_MAX_LINE_CHARS = 160
_FRAME_STYLE = {"position", "width", "height"}
_IMAGE_STYLE = _FRAME_STYLE | {"left", "top", "border-color"}
_LABEL_STYLE = {"position", "left", "top", "font-size", "color", "font-weight"}


def _declarations(attrs):
    styles = [value for name, value in attrs if name == "style"]
    if len(styles) != 1 or not isinstance(styles[0], str) or len(styles[0]) > 512:
        return {}
    result = {}
    for part in styles[0].split(";"):
        if not part.strip():
            continue
        name, sep, value = part.partition(":")
        name = name.strip().lower()
        if not sep or name in result:
            return {}
        result[name] = value.strip().lower()
    return result


def _pixels(style, field, *, allow_points=False):
    match = _PIXELS.fullmatch(style.get(field, ""))
    if match is None or (match[2] == "pt" and not allow_points):
        return None
    value = float(match[1])
    return round(value * 4 / 3, 6) if match[2] == "pt" else value


def valid_figure_layout(layout):
    if not isinstance(layout, dict) or set(layout) != {"width", "height", "labels"}:
        return False

    def between(value, low, high):
        return type(value) in (int, float) and low <= value <= high and math.isfinite(value)

    width, height, labels = layout["width"], layout["height"], layout["labels"]
    if (not between(width, 1, 10000) or not between(height, 1, 10000)
            or not isinstance(labels, list) or not 1 <= len(labels) <= _MAX_LABELS):
        return False
    for label in labels:
        if (not isinstance(label, dict) or set(label) != {"left", "top", "font_size", "lines"}
                or not between(label["left"], 0, width) or not between(label["top"], 0, height)
                or not between(label["font_size"], 5, 72)):
            return False
        lines = label["lines"]
        if (not isinstance(lines, list) or not 1 <= len(lines) <= _MAX_LINES
                or not all(isinstance(line, str) and 1 <= len(line) <= _MAX_LINE_CHARS
                           and line == " ".join(line.split()) for line in lines)):
            return False
    return True


@dataclass
class _Frame:
    width: float
    height: float
    image: tuple[int, int] | None = None
    labels: list[dict] = field(default_factory=list)
    paragraphs: list[tuple[int, int]] = field(default_factory=list)
    paragraph: tuple[tuple[int, int], dict, list[str]] | None = None
    invalid: bool = False
    div_depth: int = 1


class _FigureParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.frame = None
        self.figures = {}
        self.paragraphs = {}

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        frame = self.frame
        if frame is None:
            if tag == "div" and "overlayedimage" in attributes and "hidden" not in attributes:
                style = _declarations(attrs)
                width, height = _pixels(style, "width"), _pixels(style, "height")
                if set(style) == _FRAME_STYLE and style["position"] == "relative" and width and height:
                    self.frame = _Frame(width, height)
            return
        if tag == "div":
            frame.div_depth += 1
            frame.invalid = True
        if frame.invalid:
            return
        if frame.paragraph is not None:
            if tag == "br" and not attrs and len(frame.paragraph[2]) < _MAX_LINES:
                frame.paragraph[2].append("")
            else:
                frame.invalid = True
            return
        style = _declarations(attrs)
        if (tag == "img" and frame.image is None and "overlayedimage" in attributes
                and set(style) <= _IMAGE_STYLE and style.get("position") == "absolute"
                and "hidden" not in attributes
                and _pixels(style, "left") == _pixels(style, "top") == 0
                and _pixels(style, "width") == frame.width and _pixels(style, "height") == frame.height):
            frame.image = self.getpos()
        elif (tag == "p" and frame.image is not None and len(frame.labels) < _MAX_LABELS
              and set(style) == _LABEL_STYLE and style["position"] == "absolute" and style["color"] == "black"
              and style.get("font-weight") == "normal" and set(attributes) <= {"id", "style"}):
            label = {"left": _pixels(style, "left"), "top": _pixels(style, "top"),
                     "font_size": _pixels(style, "font-size", allow_points=True)}
            frame.paragraph = (self.getpos(), label, [""])
        else:
            frame.invalid = True

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in {"br", "img"}:
            self.handle_endtag(tag)

    def handle_data(self, data):
        if self.frame is None or self.frame.invalid:
            return
        if self.frame.paragraph is not None:
            lines = self.frame.paragraph[2]
            lines[-1] += data
            if len(lines[-1]) > 512:
                self.frame.invalid = True
        elif data.strip():
            self.frame.invalid = True

    def handle_endtag(self, tag):
        frame = self.frame
        if frame is None:
            return
        if tag == "p" and not frame.invalid and frame.paragraph is not None:
            position, label, lines = frame.paragraph
            label["lines"] = [" ".join(line.split()) for line in lines]
            frame.labels.append(label)
            frame.paragraphs.append(position)
            frame.paragraph = None
        elif tag == "div":
            frame.div_depth -= 1
            if frame.div_depth == 0:
                self.frame = None
                layout = {"width": frame.width, "height": frame.height, "labels": frame.labels}
                if not frame.invalid and frame.paragraph is None and frame.image is not None and valid_figure_layout(layout):
                    self.figures[frame.image] = layout
                    self.paragraphs.update(dict.fromkeys(frame.paragraphs, frame.image))
        else:
            frame.invalid = True


def read_positioned_figures(html):
    if _OVERLAID_MARKER.search(html) is None:
        return {}, {}
    parser = _FigureParser()
    parser.feed(html)
    parser.close()
    return parser.figures, parser.paragraphs
