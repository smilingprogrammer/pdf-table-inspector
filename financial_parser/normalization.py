"""Derived values only; raw cells and financial meaning are untouched."""
from .numbers import parse_number


def normalize(tables, config):
    return {cell.id: {'text': cell.raw_text.strip()
                     if config.strip_normalized_text and cell.raw_text is not None
                     else cell.raw_text,
                     'number': parse_number(cell.raw_text, config.number_profile).to_dict()}
            for table in tables for cell in table.cells}
