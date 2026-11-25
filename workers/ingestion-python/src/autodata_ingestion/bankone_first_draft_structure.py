"""Recover exact Bankone authoring boundaries lost in the prose projection."""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from hashlib import sha256
from html.parser import HTMLParser
import re

from . import procedure_rewrite_auto as auto, procedure_rewrite_full as full
from .article_lifecycle_types import digest_json
from .procedure_rewrite_recovery import _PART, _REFERENCE, _plain_label


_INVALID = "BANKONE_STRUCTURE_INVALID"
_SPACE = re.compile(r"\s+")
_FINAL_OR = re.compile(r"or\b\s+", re.IGNORECASE)
_OR_WORD = re.compile(r"\bor\b", re.IGNORECASE)
_TOOL_HEADING = re.compile(r"(?:(?:special|required|service) )?tools?(?: required)?[ :]*", re.IGNORECASE)
_TOOL_ID = re.compile(r"[a-z0-9]+(?:[./-]+[a-z0-9]+)*", re.IGNORECASE | re.ASCII)
_ROOT_PARAGRAPH = re.compile(r"/blocks/([0-9]+)/text")
_ROOT_LIST_ITEM = re.compile(r"/blocks/([0-9]+)/items/[0-9]+(?:/text)?")
_PROCEDURE_SECTION = re.compile(r"(Removal|Installation) (?:procedure|instructions|steps)", re.I)
_SINGLE_LINK_DIRECTIVE = re.compile(
    rf"(?P<part>{_PART}) ?(?P<marker>{_REFERENCE})\s*»\s*(?P<verb>Remove|Install)"
    rf"—\s*(?P<title>{_PART} Replacement)", re.I,
)
_SHA256 = re.compile(r"[0-9a-f]{64}")
_VOID_TAGS = frozenset("area base br col embed hr img input link meta param source track wbr".split())
_NONDISPLAY_TAGS = frozenset({"iframe", "noscript", "object", "script", "style", "template"})
_HIDDEN_STYLE = re.compile(r"(?:^|;)\s*(?:display\s*:\s*none|visibility\s*:\s*(?:hidden|collapse))\b", re.I)
LINKED_STRUCTURE_VERSION = 2
LINKED_STRUCTURE_KINDS = frozenset({"procedure_section", "single_link_directive"})


@dataclass(frozen=True)
class BankoneAlternatives:
    target: str
    verb: str
    suffix: str
    options: tuple[str, ...]


def bankone_procedure_section(text):
    match = _PROCEDURE_SECTION.fullmatch(text)
    return match[1].casefold() if match else None


def bankone_linked_directive(text):
    match = _SINGLE_LINK_DIRECTIVE.fullmatch(text)
    if (match and _plain_label(match["part"])
            and match["title"].casefold() == f'{match["part"]} Replacement'.casefold()):
        return match
    return None


def bankone_alternatives(text: str) -> BankoneAlternatives | None:
    """Read one arrow-led command with a serial list of alternatives."""
    if text.count("»") != 1:
        return None
    left, right = text.split("»")
    target = left.strip()
    actions = auto._action_matches(right)
    if not target or auto._action_matches(target) or len(actions) != 1:
        return None
    action = actions[0]
    verb = action.group().casefold()
    if verb not in {"remove", "install"} or re.search(r"\w", right[:action.start()]):
        return None

    suffix = right[action.end():].strip()
    start = depth = 0
    options = []
    for index, char in enumerate(suffix):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                return None
        elif char == "," and depth == 0:
            options.append(suffix[start:index].strip())
            start = index + 1
    last = suffix[start:].strip()
    final_or = _FINAL_OR.match(last)
    if depth or len(options) < 2 or not all(options) or final_or is None:
        return None
    options.append(last[final_or.end():])
    if not options[-1] or len(set(options)) != len(options) or any(_OR_WORD.search(option) for option in options):
        return None
    return BankoneAlternatives(target, verb, suffix, tuple(options))


def _compact(text):
    return _SPACE.sub(" ", text).strip()


def _bare_note(text):
    label = auto.authored_note_prefix(text)
    return label is not None and not text[len(label):].strip()


def _tool_identifier(text):
    tokens = full._technical_tokens(text)
    if len(tokens) != 1:
        return None
    [identifier] = tokens
    if (_TOOL_ID.fullmatch(identifier) and any(char.isalpha() for char in identifier)
            and any(char.isdigit() for char in identifier)
            and text.startswith(identifier + " ") and text[len(identifier):].strip()):
        return identifier
    return None


@dataclass(eq=False)
class _Element:
    tag: str
    start: int
    end: int
    parent: "_Element | None" = None
    children: list["_Element"] = field(default_factory=list)
    reference: str | None = None
    hidden: bool = False


class _Markup(HTMLParser):
    def __init__(self, html: str):
        super().__init__(convert_charrefs=True)
        self.elements = []
        self._root = _Element("", 0, 0)
        self._stack = [self._root]
        self._parts = []
        self._offset = 0
        self.feed(html)
        self.close()
        for element in self._stack:
            element.end = self._offset
        self.text = "".join(self._parts)
        self._spans = defaultdict(list)
        for element in self.elements:
            if not element.hidden and element.tag in {"li", "p", "dt"}:
                self._spans[(element.tag, self.label(element))].append(element)

    def handle_starttag(self, tag, attrs):
        parent = self._stack[-1]
        hidden = parent.hidden or tag in _NONDISPLAY_TAGS or any(
            key == "hidden" or (key == "aria-hidden" and value is not None and value.strip().casefold() == "true")
            or (key == "style" and value is not None and _HIDDEN_STYLE.search(value))
            for key, value in attrs
        )
        element = _Element(tag, self._offset, self._offset, parent, hidden=bool(hidden))
        if tag == "mtr-doc-link":
            ids = [value for key, value in attrs if key == "id"]
            if len(ids) == 1 and ids[0] and ids[0].strip() == ids[0]:
                element.reference = ids[0]
        parent.children.append(element)
        self.elements.append(element)
        if tag not in _VOID_TAGS:
            self._stack.append(element)

    def handle_endtag(self, tag):
        for index in reversed(range(1, len(self._stack))):
            if self._stack[index].tag == tag:
                for element in self._stack[index:]:
                    element.end = self._offset
                del self._stack[index:]
                return

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in _VOID_TAGS:
            self.handle_endtag(tag)

    def handle_data(self, data):
        self._parts.append(data)
        self._offset += len(data)

    def label(self, element):
        return _compact(self.text[element.start:element.end])

    def unique_span(self, tag, text):
        matches = self._spans.get((tag, _compact(text)), ())
        return matches[0] if len(matches) == 1 else None


def _descendants(element):
    pending = list(reversed(element.children))
    while pending:
        child = pending.pop()
        yield child
        pending.extend(reversed(child.children))


def _authored_note_labels(markup):
    labels = []
    for element in markup.elements:
        parent = element.parent
        if element.hidden or element.tag not in {"b", "strong"} or parent.tag != "p":
            continue
        label = markup.label(element)
        if not _bare_note(label) or _compact(markup.text[parent.start:element.start]):
            continue
        next_index = parent.children.index(element) + 1
        following = parent.children[next_index:]
        # A list starts a new block, so adjacent text outside the bold span
        # must be absent before treating the authored label as standalone.
        boundary = following[0] if following else None
        if markup.label(parent) == label or (
            boundary is not None and boundary.tag in {"ol", "ul"}
            and _compact(markup.text[parent.start:boundary.start]) == label
        ):
            labels.append(label)
    return labels


def _authored_tool_label(markup, text, identifier):
    paragraph = markup.unique_span("p", text)
    if paragraph is None or len(paragraph.children) != 1:
        return False
    [italic] = paragraph.children
    if italic.hidden or italic.tag != "i" or markup.label(italic) != identifier:
        return False
    description = paragraph.parent
    if description.tag != "dd" or description.parent.tag != "dl":
        return False
    siblings = description.parent.children
    preceding = siblings[:siblings.index(description)]
    term = next((element for element in reversed(preceding) if element.tag == "dt"), None)
    return term is not None and not term.hidden and _TOOL_HEADING.fullmatch(markup.label(term)) is not None


def _option_reference_hashes(markup, text, alternatives):
    item = markup.unique_span("li", text)
    if item is None:
        return None
    links = [element for element in _descendants(item) if element.tag == "mtr-doc-link"]
    if len(links) != len(alternatives.options) or any(link.hidden or not link.reference for link in links):
        return None
    references = [link.reference for link in links]
    if len(set(references)) != len(references):
        return None

    raw = markup.text[item.start:item.end]
    normalized = _compact(raw)
    suffix = _compact(alternatives.suffix)
    if not normalized.endswith(suffix):
        return None
    cursor = len(normalized) - len(suffix)
    for index, (link, option) in enumerate(zip(links, alternatives.options, strict=True)):
        label = markup.label(link)
        option = _compact(option)
        if not label or (label not in option if index == 0 else label != option):
            return None
        # A repeated component label can appear in several choices. Its
        # authored text offset, not substring presence, binds it to one.
        offset = len(_SPACE.sub(" ", raw[:link.start-item.start]).lstrip())
        while offset < len(normalized) and normalized[offset].isspace():
            offset += 1
        start = normalized.find(option, cursor)
        end = start + len(option)
        if (start < cursor or not start <= offset <= end - len(label)
                or normalized[offset:offset+len(label)] != label):
            return None
        cursor = end
    return [sha256(reference.encode()).hexdigest() for reference in references]


def _prose_slots(source):
    if not full._source_valid(source):
        raise ValueError(_INVALID)
    return {slot["path"]: slot for slot in full.prose_slots(source, include_cell_blocks=True)}


def _standalone_paragraph(source, path):
    match = _ROOT_PARAGRAPH.fullmatch(path)
    if match is None:
        return False
    block = source["blocks"][int(match[1])]
    return block["type"] == "paragraph" and not block.get("images")


def _ordered_list_item(source, path):
    match = _ROOT_LIST_ITEM.fullmatch(path)
    return match is not None and source["blocks"][int(match[1])]["type"] == "ordered_list"


def _authored_procedure_section(markup, text):
    term = markup.unique_span("dt", text)
    if term is None or term.children or term.parent.tag != "dl":
        return False
    siblings = term.parent.children
    following = siblings[siblings.index(term) + 1:]
    return bool(following and following[0].tag == "dd" and not following[0].hidden and markup.label(following[0]))


def _single_link_reference_hash(markup, text, directive):
    item = markup.unique_span("li", text)
    if item is None or item.parent.tag != "ol" or len(item.children) != 1:
        return None
    [link] = item.children
    if (link.hidden or link.tag != "mtr-doc-link" or link.children or not link.reference
            or markup.label(link) != directive["title"] or markup.text[link.end:item.end].strip()):
        return None
    return sha256(link.reference.encode()).hexdigest()


def _linked_slots(source, prose, markup):
    duplicates = Counter(_compact(slot["text"]) for slot in prose.values())
    for path, slot in prose.items():
        text = slot["text"]
        if duplicates[_compact(text)] != 1:
            continue
        if (_standalone_paragraph(source, path) and bankone_procedure_section(text)
                and _authored_procedure_section(markup, text)):
            yield path, {"block_id": slot["block_id"], "kind": "procedure_section"}
        elif _ordered_list_item(source, path) and (directive := bankone_linked_directive(text)):
            if reference_hash := _single_link_reference_hash(markup, text, directive):
                yield path, {"block_id": slot["block_id"], "kind": "single_link_directive",
                             "reference_hash": reference_hash}


def extract_bankone_structure(source: dict, html: bytes, *, version: int = 1) -> dict:
    """Build an exact, JSON-safe proof from a caller-verified retained body."""
    prose = _prose_slots(source)
    if not isinstance(html, bytes) or type(version) is not int or version not in (1, LINKED_STRUCTURE_VERSION):
        raise ValueError(_INVALID)
    try:
        markup = _Markup(html.decode("utf-8-sig"))
    except ValueError:
        raise ValueError(_INVALID) from None
    slots = {}
    notes = [slot for path, slot in prose.items()
             if _standalone_paragraph(source, path) and _bare_note(slot["text"])]
    if [slot["text"] for slot in notes] == _authored_note_labels(markup):
        for slot in notes:
            slots[slot["path"]] = {"block_id": slot["block_id"], "kind": "note_label"}
    for path, slot in prose.items():
        value = slot["text"]
        block_id = slot["block_id"]
        if alternatives := bankone_alternatives(value):
            hashes = _option_reference_hashes(markup, value, alternatives)
            if hashes is not None:
                slots[path] = {"block_id": block_id, "kind": "alternatives", "reference_hashes": hashes}
        elif _standalone_paragraph(source, path) and (identifier := _tool_identifier(value)):
            if _authored_tool_label(markup, value, identifier):
                slots[path] = {"block_id": block_id, "kind": "tool_label"}
    proof = {"source_hash": digest_json(source), "slots": slots}
    if version == LINKED_STRUCTURE_VERSION:
        proof["version"] = version
        slots.update(_linked_slots(source, prose, markup))
    return proof


def validate_bankone_structure(source, proof, *, expected_version=None) -> None:
    """Check exact proof shape against the immutable source prose slots."""
    prose = _prose_slots(source)
    if not isinstance(proof, dict):
        raise ValueError(_INVALID)
    version = proof.get("version", 1)
    fields = {"source_hash", "slots", "version"} if version == LINKED_STRUCTURE_VERSION else {"source_hash", "slots"}
    if (type(version) is not int or version not in (1, LINKED_STRUCTURE_VERSION)
            or (expected_version is not None and version != expected_version)
            or set(proof) != fields or proof["source_hash"] != digest_json(source)
            or not isinstance(proof["slots"], dict)):
        raise ValueError(_INVALID)
    counts = Counter(_compact(slot["text"]) for slot in prose.values()) if version == LINKED_STRUCTURE_VERSION else {}
    for path, entry in proof["slots"].items():
        slot = prose.get(path)
        if slot is None or not isinstance(entry, dict) or entry.get("block_id") != slot["block_id"]:
            raise ValueError(_INVALID)
        kind = entry.get("kind")
        value = slot["text"]
        if not isinstance(kind, str):
            raise ValueError(_INVALID)
        if kind == "alternatives":
            alternatives = bankone_alternatives(value)
            hashes = entry.get("reference_hashes")
            if (set(entry) != {"block_id", "kind", "reference_hashes"} or alternatives is None
                    or not isinstance(hashes, list) or len(hashes) != len(alternatives.options)
                    or not all(isinstance(digest, str) and _SHA256.fullmatch(digest) for digest in hashes)
                    or len(set(hashes)) != len(hashes)):
                raise ValueError(_INVALID)
        elif version == LINKED_STRUCTURE_VERSION and kind in LINKED_STRUCTURE_KINDS:
            if counts[_compact(value)] != 1:
                raise ValueError(_INVALID)
            if kind == "procedure_section":
                if (set(entry) != {"block_id", "kind"} or not _standalone_paragraph(source, path)
                        or bankone_procedure_section(value) is None):
                    raise ValueError(_INVALID)
            else:
                reference_hash = entry.get("reference_hash")
                if (set(entry) != {"block_id", "kind", "reference_hash"} or not _ordered_list_item(source, path)
                        or bankone_linked_directive(value) is None or not isinstance(reference_hash, str)
                        or not _SHA256.fullmatch(reference_hash)):
                    raise ValueError(_INVALID)
        elif (set(entry) != {"block_id", "kind"} or not _standalone_paragraph(source, path)
              or not ((kind == "note_label" and _bare_note(value))
                      or (kind == "tool_label" and _tool_identifier(value)))):
            raise ValueError(_INVALID)
