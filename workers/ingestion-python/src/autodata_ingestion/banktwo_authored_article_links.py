"""Bind Banktwo GUID anchors to the exact immutable article slots."""

from collections import Counter
from hashlib import sha256
import json
import re
from urllib.parse import parse_qs, urlsplit

from .bankone_first_draft_structure import _Markup, _compact, _descendants
from .retained_inline_article_links import _exact_label, _slots
from .source_connector_client import _valid_article_link_bindings


_GUID_PATH = re.compile(r"/api/v1/content/carids/[0-9]{1,20}/guid/[A-Za-z0-9_-]{1,160}")
_INLINE_TAGS = frozenset({"b", "em", "font", "i", "small", "span", "strong", "sub", "sup", "u"})
_MAX_LINKS = 128


class _BanktwoMarkup(_Markup):
    def handle_starttag(self, tag, attrs):
        super().handle_starttag(tag, attrs)
        element = self.elements[-1]
        if tag == "a" and ("class", "image") in attrs:
            element.hidden = True
        if tag != "a" or element.hidden:
            return
        refs = [value for name, value in attrs if name == "href"]
        if len(refs) != 1 or not refs[0]:
            return
        path = refs[0]
        if path.startswith('\\"') and path.endswith('\\"'):
            path = path[2:-2]
        if _GUID_PATH.fullmatch(path):
            element.reference = path

    def handle_data(self, data):
        if not self._stack[-1].hidden:
            super().handle_data(data)

    def anchors(self, span):
        for element in _descendants(span):
            if element.hidden or element.tag != "a" or not element.reference:
                continue
            parent = element.parent
            while parent is not span and parent.tag in _INLINE_TAGS:
                parent = parent.parent
            if parent is span:
                yield element


def _digest(value):
    return sha256(value.encode()).hexdigest()


def banktwo_article_markup(raw, media_type):
    """Read the markup covered by the Banktwo connector's authored lookup."""
    if media_type not in {"application/json", "application/hal+json"}:
        raise ValueError("BANKTWO_AUTHORED_ARTICLE_BODY_INVALID")
    value = json.loads(raw)
    embedded = value.get("_embedded") if isinstance(value, dict) else None
    data = embedded.get("data") if isinstance(embedded, dict) else None
    if not isinstance(data, dict):
        raise ValueError("BANKTWO_AUTHORED_ARTICLE_BODY_INVALID")
    article = data.get("article")
    if isinstance(article, dict):
        structured = any(isinstance(article.get(key), list) and article[key] for key in ("blocks", "steps"))
        for name in ("content",) if structured else ("body", "text", "content", "html"):
            markup = article.get(name)
            if isinstance(markup, str) and markup.strip():
                return markup
    elif article is None and "partsAndLabor" not in data:
        markup = data.get("content")
        if isinstance(markup, str) and markup.strip():
            return markup
    raise ValueError("BANKTWO_AUTHORED_ARTICLE_BODY_INVALID")


def banktwo_authored_guid_paths(html):
    """Return distinct visible same-document GUID paths in supplier order."""
    paths = dict.fromkeys(element.reference for element in _BanktwoMarkup(html).elements
                          if element.tag == "a" and element.reference)
    if len(paths) > _MAX_LINKS:
        raise ValueError("INLINE_ARTICLE_LINK_LIMIT")
    return list(paths)


def preserve_guid_index(resource, document, title):
    """Keep exact labels when the entire bound GUID document is a link index."""
    blocks = document["blocks"]
    if not blocks or len(blocks) > _MAX_LINKS + 1:
        return False
    title_block = blocks[0] if blocks[0]["type"] == "paragraph" and blocks[0]["text"] == title else None
    choices = [block for block in blocks if block is not title_block and block["type"] != "heading"]
    if not choices or any(block["type"] != "paragraph" for block in choices):
        return False
    locator = urlsplit(resource.source_uri)
    query = parse_qs(locator.query, keep_blank_values=True)
    path = locator.path
    if query:
        if set(query) != {"path"} or len(query["path"]) != 1:
            return False
        path = query["path"][0]
    if locator.fragment or not _GUID_PATH.fullmatch(path):
        return False
    vehicle_prefix, _, _ = path.rpartition("/guid/")
    try:
        markup = _BanktwoMarkup(banktwo_article_markup(resource.payload, resource.media_type))
    except ValueError:
        return False
    authored = []
    for element in markup.elements:
        if element.hidden or element.tag != "p":
            continue
        anchors = tuple(markup.anchors(element))
        if len(anchors) == 1:
            anchor = anchors[0]
            label = markup.label(anchor)
            if label == markup.label(element) and anchor.reference != path and anchor.reference.startswith(vehicle_prefix + "/guid/"):
                authored.append((label, anchor.reference))
    if (len(authored) != len(choices)
            or [_compact(block["text"]) for block in choices] != [label for label, _ in authored]
            or len({label for label, _ in authored}) != len(choices)
            or len({target for _, target in authored}) != len(choices)):
        return False
    if title_block:
        title_block.update(type="heading", level=2)
    for choice in choices:
        choice["type"] = "link"
    return True


def _banktwo_slots(document):
    slots = _slots(document)
    for block in document.get("blocks", ()):
        if block["type"] == "link" and not block.get("href") and not block.get("target_ref_sha256"):
            slots[block["block_id"], -1] = ("p", block["text"], None)
    return slots


def banktwo_inline_article_links(html, connector_bindings, source_document, canonical_document):
    """Project only labels that occur at the same authored source and reader locations."""
    if not _valid_article_link_bindings(connector_bindings):
        return []
    targets = {item["source_id_sha256"]: item["target_ref_sha256"] for item in connector_bindings}
    source_slots = _banktwo_slots(source_document)
    reader_slots = _banktwo_slots(canonical_document)
    count_by_span = Counter((tag, _compact(text)) for tag, text, _ in source_slots.values())
    markup = _BanktwoMarkup(html)
    resolved_by_span = {}
    for span in markup.elements:
        if span.hidden or span.tag not in {"p", "li"}:
            continue
        text = markup.label(span)
        key = (span.tag, text)
        if key not in count_by_span:
            continue
        hits = []
        for anchor in markup.anchors(span):
            label, authored = markup.label(anchor), _digest(anchor.reference)
            if authored in targets and len(label.encode()) <= 384 and _exact_label(text, label):
                hits.append((label, authored, targets[authored]))
        resolved_by_span.setdefault(key, []).append(tuple(hits))

    links = []
    for (block, index), (tag, text, _) in source_slots.items():
        reader = reader_slots.get((block, index))
        if not reader or reader[0] != tag:
            continue
        key = (tag, _compact(text))
        matches = resolved_by_span.get(key, ())
        # Repeated identical text is safe only when each authored occurrence
        # has the same links and its source slot counterpart is present.
        if (not matches or len(matches) != count_by_span[key]
                or any(match != matches[0] for match in matches)):
            continue
        for label, authored, target in matches[0]:
            if _exact_label(text, label) and _exact_label(reader[1], label):
                links.append({
                    "block_id": block, "item_index": index, "label": label, "label_sha256": _digest(label),
                    "authored_id_sha256": authored, "target_ref_sha256": target,
                })
    if len(links) > _MAX_LINKS:
        raise ValueError("INLINE_ARTICLE_LINK_LIMIT")
    return sorted(links, key=lambda item: (item["block_id"], item["item_index"], item["label_sha256"]))
