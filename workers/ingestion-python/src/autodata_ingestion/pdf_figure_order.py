"""Find a visible gap for a directly drawn figure on a simple native PDF page."""

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


def figure_text_gap(page, text, segments):
    """Find an insertion slot without changing the existing native text blocks."""
    lines = text.splitlines()
    if len(lines) < 2 or lines != [block.get("text") for block in segments]:
        return None

    bounds = []
    text_boxes = []

    def visit_operand(operator, operands, matrix, _text_matrix):
        if operator in _AMBIGUOUS_OPERATORS:
            raise ValueError("ambiguous painted content")
        if operator == b"Do":
            if bounds or operands != [image_key] or not _upright_matrix(matrix):
                raise ValueError("ambiguous figure placement")
            width, _, _, height, x, y = matrix
            bounds.append((x, y, x + width, y + height))

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
        image_keys = page.images.keys()
        if (
            page.rotation != 0 or page.get("/Annots")
            or len(image_keys) != 1 or not isinstance(image_keys[0], str)
        ):
            return None
        image_key = image_keys[0]
        image = page["/Resources"]["/XObject"][image_key]
        if image.get("/Subtype") != "/Image" or any(key in image for key in ("/Mask", "/SMask", "/OC")):
            return None
        crop_left, crop_bottom, crop_right, crop_top = map(float, page.cropbox)
        page.extract_text(visitor_operand_before=visit_operand, visitor_text=visit_text)
    except Exception:
        # This optional layout pass must never replace usable text or images.
        return None

    if not bounds or len(text_boxes) != len(lines):
        return None
    [(left, bottom, right, top)] = bounds
    if not (crop_left <= left < right <= crop_right and crop_bottom <= bottom < top <= crop_top):
        return None
    column_left = text_boxes[0][0]
    if any(
        not (abs(x - column_left) <= 2 and crop_left <= x and left - 2 <= x < right
             and crop_bottom <= y - height and y + height <= crop_top)
        for x, y, height in text_boxes
    ):
        return None
    if any(first[1] <= second[1] for first, second in zip(text_boxes, text_boxes[1:])):
        # Drawing order is not reading order. Keep the original text order.
        return None
    for index, (_, y, height) in enumerate(text_boxes):
        if y - height > top:
            continue
        if index and all(y + height < bottom for _, y, height in text_boxes[index:]):
            return index
        break
    return None
