"""Deterministic PDF rendering for an already validated repair guide."""

from __future__ import annotations

from io import BytesIO
import re
from typing import Any, Mapping


_GENERIC_FIGURE_CAPTIONS = frozenset({
    "diagram",
    "figure",
    "image",
    "picture",
    "procedure figure",
    "source diagram",
})


def _figure_caption(image: Mapping[str, Any]) -> str:
    """Return a useful caption without exposing source placeholder labels."""

    for key in ("alt", "description", "label", "title"):
        value = str(image.get(key) or "").strip()
        if value and value.casefold() not in _GENERIC_FIGURE_CAPTIONS:
            return value
    return ""


def render_guide_pdf(guide: Mapping[str, Any]) -> bytes:
    if guide.get("content_status") != "complete" or guide.get("pdf_ready") is not True:
        raise ValueError("a complete guide is required before creating a PDF")
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.pdfbase.pdfmetrics import stringWidth
        from reportlab.platypus import Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as error:  # pragma: no cover - deployment dependency failure
        raise RuntimeError("PDF rendering dependency is not installed") from error

    styles = getSampleStyleSheet()
    title = ParagraphStyle("GuideTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=20, leading=24, alignment=TA_CENTER, textColor=colors.HexColor("#17231f"), spaceAfter=8)
    subtitle = ParagraphStyle("GuideSubtitle", parent=styles["Normal"], fontName="Helvetica", fontSize=10, leading=13, alignment=TA_CENTER, textColor=colors.HexColor("#53625c"), spaceAfter=18)
    heading = ParagraphStyle("GuideHeading", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=13, leading=16, textColor=colors.HexColor("#17231f"), spaceBefore=12, spaceAfter=7)
    step = ParagraphStyle("GuideStep", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=10.5, leading=14, textColor=colors.HexColor("#17231f"), spaceAfter=4)
    body = ParagraphStyle("GuideBody", parent=styles["BodyText"], fontName="Helvetica", fontSize=9.5, leading=13, textColor=colors.HexColor("#27352f"), spaceAfter=5)
    small = ParagraphStyle("GuideSmall", parent=body, fontSize=8, leading=10, textColor=colors.HexColor("#53625c"))
    warning = ParagraphStyle("GuideWarning", parent=body, backColor=colors.HexColor("#fff5df"), borderColor=colors.HexColor("#e7b24a"), borderWidth=0.5, borderPadding=7, spaceBefore=4, spaceAfter=7)

    def esc(value: Any) -> str:
        from xml.sax.saxutils import escape

        return escape(str(value or ""))

    story: list[Any] = [Paragraph(esc(guide.get("title") or "DIY Repair Guide"), title), Paragraph(esc(guide.get("applicability") or "Vehicle-specific procedure"), subtitle)]
    preparation = guide.get("preparation", [])
    if isinstance(preparation, list) and preparation:
        story.append(Paragraph("Before you begin", heading))
        for item in preparation:
            story.append(Paragraph(esc(item), body))
    warnings = guide.get("warnings", [])
    if isinstance(warnings, list) and warnings:
        story.append(Paragraph("Safety notes", heading))
        for item in warnings:
            message = item.get("message") if isinstance(item, Mapping) else item
            story.append(Paragraph("<b>Important:</b> " + esc(message), warning))
    story.append(Paragraph("Procedure", heading))
    steps = guide.get("steps", [])
    for index, item in enumerate(steps if isinstance(steps, list) else [], 1):
        if not isinstance(item, Mapping):
            continue
        sequence = item.get("sequence", index)
        raw_action = item.get("action")
        action = str(raw_action).strip() if raw_action else f"Step {sequence}"
        if raw_action:
            action = re.sub(rf"^\s*(?:step\s*)?{int(sequence)}\s*[.):-]\s*", "", action, flags=re.IGNORECASE)
        contents: list[Any] = [Paragraph(f"{int(sequence):02d}  {esc(action)}", step)]
        instructions = item.get("instructions", [])
        if isinstance(instructions, str):
            instructions = [instructions]
        if isinstance(instructions, list):
            for instruction in instructions:
                contents.append(Paragraph(esc(instruction), body))
        images = item.get("images", [])
        if isinstance(images, list):
            for image in images:
                if not isinstance(image, Mapping) or not image.get("image_bytes"):
                    continue
                try:
                    rendered = Image(BytesIO(image["image_bytes"]))
                    rendered._restrictSize(6.35 * inch, 3.8 * inch)
                    contents.extend([Spacer(1, 4), rendered])
                    caption = _figure_caption(image)
                    if caption:
                        contents.append(Paragraph(esc(caption), small))
                except Exception:
                    continue
        story.append(KeepTogether(contents))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Use the final checks in the last procedure steps before returning the vehicle to service.", small))

    output = BytesIO()
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#d8e0db"))
        canvas.line(doc.leftMargin, 0.55 * inch, letter[0] - doc.rightMargin, 0.55 * inch)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#53625c"))
        canvas.drawString(doc.leftMargin, 0.36 * inch, "AutoData DIY service guide")
        canvas.drawRightString(letter[0] - doc.rightMargin, 0.36 * inch, f"Page {doc.page}")
        canvas.restoreState()

    document = SimpleDocTemplate(output, pagesize=letter, rightMargin=0.7 * inch, leftMargin=0.7 * inch, topMargin=0.65 * inch, bottomMargin=0.75 * inch, title=str(guide.get("title") or "DIY Repair Guide"), author="AutoData")
    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()


__all__ = ["render_guide_pdf"]
