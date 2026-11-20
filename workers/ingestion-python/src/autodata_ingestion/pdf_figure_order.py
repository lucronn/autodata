"""Find visible gaps for directly drawn figures on a simple native PDF page."""

import math
import re


_AMBIGUOUS_OPERATORS = frozenset({
    b"W", b"W*", b"gs", b"Tr", b"Ts", b"BDC", b"INLINE IMAGE",
})


def _upright_matrix(matrix):
    return (
        len(matrix) == 6 and all(math.isfinite(value) for value in matrix)
        and matrix[0] > 0 and matrix[3] > 0 and matrix[1] == matrix[2] == 0
    )


def figure_text_gaps(page, text, segments, page_image_keys):
    """Find insertion slots in visual order without changing the native text."""
    lines = text.splitlines()
    if (len(lines) < 2 or lines != [block.get("text") for block in segments]
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
    gaps = {}
    for key, (left, bottom, right, top) in ordered:
        if not (crop_left <= left < right <= crop_right and crop_bottom <= bottom < top <= crop_top):
            return {}
        if any(not left - 2 <= x < right for x, _, _ in text_boxes):
            return {}
        gap = next((i for i, (_, y, height) in enumerate(text_boxes) if y - height <= top), len(text_boxes))
        if not 0 < gap < len(text_boxes) or any(y + height >= bottom for _, y, height in text_boxes[gap:]):
            return {}
        gaps[key] = gap
    return gaps
