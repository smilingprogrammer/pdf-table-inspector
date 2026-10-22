"""Extraction geometry only. Indices are zero-based; boxes use PDF points,
top-left origin: (x0, top, x1, bottom). IDs are scoped to source bytes and position.
"""
from dataclasses import asdict, dataclass

BBox = tuple[float, float, float, float]


@dataclass(frozen=True)
class Cell:
    id: str
    raw_text: str | None
    row: int
    column: int
    row_span: int
    column_span: int
    bbox: BBox | None


@dataclass(frozen=True)
class TableCandidate:
    id: str
    page: int
    bbox: BBox
    row_count: int
    column_count: int
    cells: tuple[Cell, ...]
    csv: str
    needs_review: bool = True

    def to_dict(self):
        result = asdict(self)
        # Convenience matrix only; cells remain the canonical structure.
        rows = [[None] * self.column_count for _ in range(self.row_count)]
        for cell in self.cells:
            rows[cell.row][cell.column] = cell.raw_text
        result['rows'] = rows
        result['dimensions'] = {'rows': self.row_count, 'columns': self.column_count}
        return result


def candidate_from_pdfplumber(table, document_id, page, index, csv):
    """Map detected rectangles onto their geometric grid, retaining merged spans.

    A missing detector slot has raw_text=None and bbox=None; an actual blank
    rectangle has raw_text=''. Covered slots of merged cells have no extra cell.
    No header removal, label lookup, or financial classification occurs here.
    """
    extracted = table.extract()
    boxes = [tuple(box) for box in table.cells if box is not None]
    xs = sorted({x for box in boxes for x in (box[0], box[2])})
    ys = sorted({y for box in boxes for y in (box[1], box[3])})
    texts = {}
    for r, row in enumerate(table.rows):
        for c, box in enumerate(row.cells):
            if box is not None:
                texts.setdefault(tuple(box), extracted[r][c])
    table_id = f'{document_id}:p{page}:t{index}'
    cells = []
    covered = set()
    for box in sorted(set(boxes), key=lambda b: (b[1], b[0])):
        col, row = xs.index(box[0]), ys.index(box[1])
        col_span = xs.index(box[2]) - col
        row_span = ys.index(box[3]) - row
        cells.append(Cell(f'{table_id}:r{row}:c{col}', texts[box], row, col,
                          row_span, col_span, box))
        covered.update((r, c) for r in range(row, row + row_span)
                       for c in range(col, col + col_span))
    for row in range(len(ys) - 1):
        for col in range(len(xs) - 1):
            if (row, col) not in covered:
                cells.append(Cell(f'{table_id}:r{row}:c{col}', None, row, col, 1, 1, None))
    return TableCandidate(table_id, page, tuple(table.bbox), len(ys) - 1,
                          len(xs) - 1, tuple(sorted(cells, key=lambda c: (c.row, c.column))), csv)
