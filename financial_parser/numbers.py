"""Strict numeric syntax profiles. Currency and scale are deliberately absent."""
from dataclasses import asdict, dataclass
from decimal import Decimal
import re


@dataclass(frozen=True)
class NumberProfile:
    name: str
    decimal_separator: str
    grouping_separator: str


PROFILES = {
    'comma-dot': NumberProfile('comma-dot', '.', ','),
    'dot-comma': NumberProfile('dot-comma', ',', '.'),
    'space-dot': NumberProfile('space-dot', '.', ' '),
    'space-comma': NumberProfile('space-comma', ',', ' '),
}


@dataclass(frozen=True)
class ParsedNumber:
    raw_text: str | None
    status: str
    value: Decimal | None = None
    profile: str = 'auto'
    sign_style: str | None = None
    negative_zero: bool = False
    # Alternative interpretations remain inspectable when automatic parsing abstains.
    interpretations: tuple[dict, ...] = ()

    def to_dict(self):
        return asdict(self)


# Targeted width conversion, NOT NFKC: superscript footnotes must not become digits.
WIDTH_MAP = str.maketrans({**{chr(0xff10+i):str(i) for i in range(10)},
                          '，':',', '．':'.', '＋':'+', '－':'-',
                          '（':'(', '）':')', '\u3000':' ',
                          '\u00a0':' ', '\u202f':' ', '−':'-'})
DASHES = {'-', '－', '—', '–', '―', '−'}


def _magnitude(text, profile):
    group = re.escape(profile.grouping_separator)
    decimal = re.escape(profile.decimal_separator)
    integer = rf'(?:[0-9]+|[0-9]{{1,3}}(?:{group}[0-9]{{3}})+)'
    if not re.fullmatch(rf'{integer}(?:{decimal}[0-9]+)?', text):
        return None
    canonical = text.replace(profile.grouping_separator, '').replace(profile.decimal_separator, '.')
    return Decimal(canonical)


def parse_number(raw_text, profile='auto'):
    """Return Decimal only for a whole-string match; never strip footnotes/currency.

    Surrounding whitespace and selected width variants are accepted in a derived
    view. A triangle, minus, or parentheses is exactly one negative sign form.
    """
    if profile != 'auto' and profile not in PROFILES:
        raise ValueError(f'Unknown number profile: {profile}')
    if raw_text is None:
        return ParsedNumber(raw_text, 'missing', profile=profile)
    stripped = raw_text.strip()
    if not stripped:
        return ParsedNumber(raw_text, 'blank', profile=profile)
    if stripped in DASHES:
        return ParsedNumber(raw_text, 'dash', profile=profile)
    text = stripped.translate(WIDTH_MAP)
    sign_style = 'unsigned'
    negative = False
    if text.startswith('(') and text.endswith(')'):
        sign_style, negative, text = 'parentheses', True, text[1:-1]
    elif text[:1] in ('△', '-', '+'):
        sign_style = {'△':'triangle', '-':'minus', '+':'plus'}[text[0]]
        negative = text[0] != '+'
        text = text[1:]
    # Any extra sign, marker, punctuation, newline or label now fails the grammar.
    interpretations = []
    for name, candidate in (PROFILES.items() if profile == 'auto' else [(profile,PROFILES[profile])]):
        value = _magnitude(text, candidate)
        if value is not None:
            if negative:
                value = value.copy_negate()  # preserve both Decimal precision and signed zero
            interpretations.append({'profile':name, 'value':value})
    if not interpretations:
        return ParsedNumber(raw_text, 'unparsed', profile=profile, sign_style=sign_style)
    distinct = {item['value'] for item in interpretations}
    if len(distinct) != 1:
        return ParsedNumber(raw_text, 'ambiguous', profile=profile, sign_style=sign_style,
                            interpretations=tuple(interpretations))
    value = interpretations[0]['value']
    return ParsedNumber(raw_text, 'number', value, profile, sign_style,
                        value.is_zero() and value.is_signed(), tuple(interpretations))
