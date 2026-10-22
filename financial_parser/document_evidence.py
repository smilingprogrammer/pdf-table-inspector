"""Conservative unit evidence recognition, separate from numeric syntax.

Only explicit supported unit labels are recognized; unsupported labels stay in
page text. Amounts are never multiplied by these scales during parsing.
"""
from decimal import Decimal


UNIT_RULES = (
    (r'単位\s*[:：]\s*千円', 'JPY', Decimal('1000')),
    (r'単位\s*[:：]\s*百万円', 'JPY', Decimal('1000000')),
    (r'単位\s*[:：]\s*円', 'JPY', Decimal('1')),
    (r'(?i)\bUSD\s+in\s+thousands\b', 'USD', Decimal('1000')),
    (r'(?i)\bEUR\s+in\s+thousands\b', 'EUR', Decimal('1000')),
)


def extract_unit_evidence(page):
    evidence = []
    for pattern, currency, scale in UNIT_RULES:
        for match in page.search(pattern):
            evidence.append({'raw_text':match['text'],
                'bbox':[match['x0'],match['top'],match['x1'],match['bottom']],
                'currency':currency, 'scale':scale, 'rule':pattern})
    return evidence
