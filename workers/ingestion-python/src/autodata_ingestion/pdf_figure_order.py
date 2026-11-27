"""Find visible gaps for directly drawn figures on a simple native PDF page."""

import math
import re


_AMBIGUOUS_OPERATORS = frozenset({
    b"W", b"W*", b"gs", b"Tr", b"Ts", b"BDC", b"INLINE IMAGE",
})

_WORDLESS_TEXT_SETUP = frozenset({b"Tf", b"TL"})
_PATH_BUILDERS = frozenset({b"m", b"l", b"c", b"v", b"y", b"h", b"re"})
_PATH_PAINTS = frozenset({b"S", b"s", b"f", b"F", b"f*", b"B", b"B*", b"b", b"b*"})


def normalized_native_pdf_text(value):
    return "\n".join(line for raw in value.splitlines() if (line := re.sub(r"[ \t]+", " ", raw).strip()))


def _upright_matrix(matrix):
    return (
        len(matrix) == 6 and all(math.isfinite(value) for value in matrix)
        and matrix[0] > 0 and matrix[3] > 0 and matrix[1] == matrix[2] == 0
    )


def is_single_wordless_figure(page, image_key):
    """Prove one direct image is the only painted content on the page."""
    if not isinstance(image_key, str):
        return False
    bounds = None
    text_open = False
    saved_states = 0

    def visit_operand(operator, operands, matrix, _text_matrix):
        nonlocal bounds, text_open, saved_states
        if (operator == b"BT" and not text_open) or (operator == b"ET" and text_open):
            text_open = not text_open
            return
        if text_open and operator in _WORDLESS_TEXT_SETUP:
            return
        if not text_open and operator in (b"q", b"Q", b"cm"):
            saved_states += int(operator == b"q") - int(operator == b"Q")
            if saved_states < 0:
                raise ValueError("invalid wordless PDF graphics state")
            return
        if (text_open or operator != b"Do" or bounds is not None or list(operands) != [image_key]
                or not _upright_matrix(matrix)):
            raise ValueError("ambiguous wordless PDF figure")
        width, _, _, height, left, bottom = matrix
        bounds = (left, bottom, width, height)

    try:
        if page.rotation != 0 or page.get("/Annots") or page.get("/Group"):
            return False
        image = page["/Resources"]["/XObject"][image_key]
        if image.get("/Subtype") != "/Image" or any(key in image for key in ("/Mask", "/SMask", "/ImageMask", "/OC")):
            return False
        if page.extract_text(visitor_operand_before=visit_operand).strip() or bounds is None or text_open or saved_states:
            return False
        crop = tuple(map(float, page.cropbox))
        media = tuple(map(float, page.mediabox))
    except Exception:
        return False

    left, bottom, width, height = bounds
    return width >= 64 and height >= 64 and all(
        all(map(math.isfinite, (x0, y0, x1, y1)))
        and x0 <= left and left + width <= x1 and y0 <= bottom and bottom + height <= y1
        for x0, y0, x1, y1 in (crop, media)
    )


def _rectangle(values):
    left, bottom, right, top = map(float, values)
    if not all(math.isfinite(value) for value in (left, bottom, right, top)) or not (left < right and bottom < top):
        raise ValueError("invalid PDF rectangle")
    return left, bottom, right, top


def _contains_figure(rectangle, figure, *, rounding=0):
    left, bottom, right, top = rectangle
    x0, y0, x1, y1 = figure
    return left <= x0 + rounding and bottom <= y0 + rounding and right >= x1 - rounding and top >= y1 - rounding


def _links_clear_of_figure(page, figure):
    x0, y0, x1, y1 = figure
    for reference in page.get("/Annots", ()):
        link = reference.get_object()
        if link.get("/Subtype") != "/Link" or link.get("/AP"):
            return False
        left, bottom, right, top = _rectangle(link["/Rect"])
        if right > x0 and left < x1 and top > y0 and bottom < y1:
            return False
    return True


def clipped_figure_text_gap(page, text, segments, image_key, *, step_parser=None):
    """Place a direct image in a proven native-text gap inside a full rectangular clip."""
    from .article_document import segment_plain_article_text

    paragraphs = [[], []]
    font_bounds = [[], []]
    phase = 0
    clip = figure = None

    def visit_operand(operator, operands, matrix, _text_matrix):
        nonlocal phase, clip, figure
        if operator in (b"W", b"W*") and not phase:
            if tuple(matrix) != (1, 0, 0, 1, 0, 0):
                raise ValueError("transformed PDF clip")
            x, y, width, height = map(float, operations[draw - 5][0])
            clip = _rectangle((x, y, x + width, y + height))
        if operator == b"Do":
            if list(operands) != [image_key] or not _upright_matrix(matrix):
                raise ValueError("ambiguous PDF figure transform")
            width, _, _, height, x, y = matrix
            figure = _rectangle((x, y, x + width, y + height))
            phase = 1

    def visit_text(value, matrix, text_matrix, font, size):
        paragraphs[phase].append(value)
        stripped = value.strip()
        if not stripped:
            return
        if (len(stripped.splitlines()) != 1 or not _upright_matrix(matrix)
                or not _upright_matrix(text_matrix) or font is None or font.get("/Subtype") != "/Type1"):
            raise ValueError("ambiguous PDF text geometry")
        bbox = font["/FontDescriptor"]["/FontBBox"]
        baseline = matrix[3] * text_matrix[5] + matrix[5]
        scale = matrix[3] * text_matrix[3] * float(size) / 1000
        bottom, top = (float(bbox[index]) * scale + baseline for index in (1, 3))
        if scale <= 0 or not math.isfinite(bottom) or not math.isfinite(top) or bottom >= top:
            raise ValueError("invalid PDF font bounds")
        font_bounds[phase].append((bottom, top))

    try:
        if page.rotation != 0 or page.get("/Group") or not isinstance(image_key, str):
            return None
        image = page["/Resources"]["/XObject"][image_key]
        if image.get("/Subtype") != "/Image" or any(key in image for key in ("/Mask", "/SMask", "/ImageMask", "/OC")):
            return None
        operations = page.get_contents().operations
        operators = [operator for _, operator in operations]
        if operators.count(b"Do") != 1:
            return None
        draw = operators.index(b"Do")
        preface, following = operators[:draw - 6], operators[draw + 3:]
        clip_scope = operators[draw - 6:draw]
        last_path = next((op for op in reversed(preface) if op in _PATH_BUILDERS | _PATH_PAINTS | {b"n"}), None)
        if (len(clip_scope) != 6 or clip_scope[2] not in (b"W", b"W*")
                or clip_scope != [b"q", b"re", clip_scope[2], b"n", b"q", b"cm"]
                or operators[draw + 1:draw + 3] != [b"Q", b"Q"]
                or preface.count(b"q") != preface.count(b"Q") or last_path in _PATH_BUILDERS
                or set(preface) & {b"W", b"W*"}
                or set(operators) & (_AMBIGUOUS_OPERATORS - {b"W", b"W*"})
                or set(following) & (_PATH_PAINTS | {b"sh"})):
            return None

        source = normalized_native_pdf_text(page.extract_text(visitor_operand_before=visit_operand, visitor_text=visit_text))
        before, after = (normalized_native_pdf_text("".join(part)) for part in paragraphs)
        if (source != text or source != before + "\n" + after or not before or not after
                or clip is None or figure is None or not all(font_bounds)):
            return None
        left, bottom, right, top = figure
        if (min(right - left, top - bottom) < 64
                or min(lower for lower, _ in font_bounds[0]) <= top
                or max(upper for _, upper in font_bounds[1]) >= bottom):
            return None
        # Permit rounding in a producer's rectangle coordinates only. Reject
        # any meaningful crop or a link annotation painted over the image.
        if (not _contains_figure(clip, figure, rounding=0.001)
                or not all(_contains_figure(_rectangle(box), figure) for box in (page.cropbox, page.mediabox))
                or not _links_clear_of_figure(page, figure)):
            return None

        leading = segment_plain_article_text(before, step_parser=step_parser)
        trailing = segment_plain_article_text(after, step_parser=step_parser)
        if leading and trailing and leading + trailing == segments:
            return len(leading)
    except Exception:
        # Geometry is optional. A PDF reader failure leaves the standard projection usable.
        return None
    return None


def figure_text_gaps(
    page, text, segments, page_image_keys, *, allow_margin_images=False, allow_single_line_figure=False,
):
    """Find insertion slots in visual order without changing the native text."""
    lines = text.splitlines()
    single_line = len(lines) == 1
    if (not lines or single_line and not allow_single_line_figure
            or lines != [block.get("text") for block in segments]
            or not page_image_keys or any(not isinstance(key, str) for key in page_image_keys)):
        return {}

    extracted_keys = set(page_image_keys)
    bounds = {}
    text_boxes = []

    def visit_operand(operator, operands, matrix, _text_matrix):
        if operator in _AMBIGUOUS_OPERATORS:
            raise ValueError("ambiguous painted content")
        if operator == b"Do":
            if len(operands) != 1 or operands[0] not in extracted_keys or not _upright_matrix(matrix):
                raise ValueError("ambiguous figure placement")
            image_key = operands[0]
            if image_key in bounds:
                raise ValueError("figure drawn more than once")
            width, _, _, height, x, y = matrix
            bounds[image_key] = (x, y, x + width, y + height)

    def visit_text(value, matrix, text_matrix, _font, font_size):
        line = re.sub(r"[ \t]+", " ", value).strip()
        if not line:
            return
        if (
            len(text_boxes) >= len(lines) or line != lines[len(text_boxes)]
            or not _upright_matrix(matrix) or not _upright_matrix(text_matrix)
        ):
            raise ValueError("ambiguous native text positions")
        x = text_matrix[4] * matrix[0] + matrix[4]
        y = text_matrix[5] * matrix[3] + matrix[5]
        height = font_size * text_matrix[3] * matrix[3]
        if not all(map(math.isfinite, (x, y, height))) or height <= 0:
            raise ValueError("invalid native text positions")
        # A full em above and below the baseline keeps near misses in the fallback.
        text_boxes.append((x, y, height))

    try:
        if page.rotation != 0 or page.get("/Annots"):
            return {}
        for image_key in page_image_keys:
            image = page["/Resources"]["/XObject"][image_key]
            if image.get("/Subtype") != "/Image" or any(key in image for key in ("/Mask", "/SMask", "/OC")):
                return {}
        crop_left, crop_bottom, crop_right, crop_top = map(float, page.cropbox)
        page.extract_text(visitor_operand_before=visit_operand, visitor_text=visit_text)
    except Exception:
        # This optional layout pass must never replace usable text or images.
        return {}

    if bounds.keys() != extracted_keys or len(text_boxes) != len(lines):
        return {}
    column_left = text_boxes[0][0]
    if any(
        not (abs(x - column_left) <= 2 and crop_left <= x and crop_bottom <= y - height and y + height <= crop_top)
        for x, y, height in text_boxes
    ):
        return {}
    if any(first[1] <= second[1] for first, second in zip(text_boxes, text_boxes[1:])):
        # Drawing order is not reading order. Keep the original text order.
        return {}
    ordered = sorted(bounds.items(), key=lambda item: item[1][3], reverse=True)
    if any(upper[1][1] <= lower[1][3] for upper, lower in zip(ordered, ordered[1:])):
        return {}
    if single_line:
        if len(ordered) != 1:
            return {}
        key, (left, bottom, right, top) = ordered[0]
        x, y, height = text_boxes[0]
        margin = (crop_top - crop_bottom) / 10
        # This narrow case admits a full-size diagram immediately below its
        # line in the page body. Header and footer art stays outside the path.
        if (abs(left - x) <= 2 and crop_left <= left < right <= crop_right
                and right - left >= 64 and top - bottom >= 64
                and crop_bottom + margin <= bottom and y + height <= crop_top - margin
                and 0 < y - height - top <= top - bottom):
            return {key: 1}
        return {}
    if allow_margin_images:
        text_top = max(y + height for _, y, height in text_boxes)
        text_bottom = min(y - height for _, y, height in text_boxes)
    gaps = {}
    for key, (left, bottom, right, top) in ordered:
        if not (crop_left <= left < right <= crop_right and crop_bottom <= bottom < top <= crop_top):
            return {}
        if allow_margin_images and (bottom > text_top or top < text_bottom):
            continue
        if any(not left - 2 <= x < right for x, _, _ in text_boxes):
            return {}
        gap = next((i for i, (_, y, height) in enumerate(text_boxes) if y - height <= top), len(text_boxes))
        if not 0 < gap < len(text_boxes) or any(y + height >= bottom for _, y, height in text_boxes[gap:]):
            return {}
        gaps[key] = gap
    return gaps
