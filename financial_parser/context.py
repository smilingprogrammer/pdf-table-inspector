"""Page text and geometry, independent of table-engine selection."""
from .document_evidence import extract_unit_evidence


def extract_context(page, config):
    text = page.extract_text() or ''
    visible = [c for c in text if not c.isspace()]
    suspect = sum(c == '\ufffd' or ord(c) < 32 for c in visible)
    usable = (len(visible) >= config.min_text_characters
              and suspect / max(1, len(visible)) < config.max_suspect_ratio)
    return {
        'size': [page.width, page.height], 'text': text,
        'character_count': len(page.chars), 'image_count': len(page.images),
        'text_status': 'text_candidate' if usable else 'review_for_ocr',
        'coordinate_system': 'PDF points; [x0, top, x1, bottom]; top-left origin',
        'characters': [{k: char[k] for k in ('text', 'x0', 'top', 'x1', 'bottom')}
                       for char in page.chars],
        'unit_evidence': extract_unit_evidence(page),
    }


def outside_text(page, tables):
    return page.filter(lambda obj: not any(
        t.bbox[0] <= (obj['x0'] + obj['x1']) / 2 <= t.bbox[2]
        and t.bbox[1] <= (obj['top'] + obj['bottom']) / 2 <= t.bbox[3]
        for t in tables)).extract_text() or ''
