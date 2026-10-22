"""Optional Camelot adapters. No DataFrame cleanup or header promotion."""
from table_models import Cell, TableCandidate
from .base import AdapterResult


class CamelotAdapter:
    def __init__(self, flavor='stream'):
        if flavor not in ('stream', 'lattice'):
            raise ValueError('Unsupported Camelot flavor')
        self.flavor = flavor
        self.name = f'camelot-{flavor}'

    def extract(self, page, config):
        # Optional dependency: importing the application does not require Camelot.
        import camelot
        from pypdf import PdfReader
        forbidden = {'pages', 'flavor', 'filepath'} & config.engine_settings.keys()
        if forbidden:
            raise ValueError(f'Use pipeline page/engine selection, not settings: {sorted(forbidden)}')
        native_page = PdfReader(page.source).pages[page.page - 1]
        if native_page.rotation or tuple(native_page.mediabox.lower_left) != (0, 0):
            raise ValueError('Camelot adapter currently requires unrotated pages with media origin (0,0)')
        height = float(native_page.mediabox.height)
        native = camelot.read_pdf(str(page.source), pages=str(page.page), flavor=self.flavor,
                                  **config.engine_settings)
        tables = []
        diagnostics = {'version': camelot.__version__, 'flavor': self.flavor,
                       'settings': config.engine_settings, 'native_tables': []}
        for index, table in enumerate(native, 1):
            table_id = f'{page.document_id}:{self.name}:p{page.page}:t{index}'
            cells = tuple(Cell(
                f'{table_id}:r{r}:c{c}', cell.text, r, c, 1, 1,
                (cell.x1, height - cell.y2, cell.x2, height - cell.y1))
                for r, row in enumerate(table.cells) for c, cell in enumerate(row))
            # Camelot's detection region can be smaller than its emitted cells.
            # Canonical table bounds enclose those cells; keep engine region separately.
            bbox = (min(c.bbox[0] for c in cells), min(c.bbox[1] for c in cells),
                    max(c.bbox[2] for c in cells), max(c.bbox[3] for c in cells))
            tables.append(TableCandidate(table_id, page.page, bbox,
                len(table.cells), len(table.cells[0]), cells,
                f'page-{page.page:03d}-table-{index:02d}.csv'))
            native_box = table._bbox
            diagnostics['native_tables'].append({
                'table_id': table_id,
                'detection_bbox': [native_box[0], height-native_box[3], native_box[2], height-native_box[1]],
                'parsing_report': table.parsing_report})
        return AdapterResult(tuple(tables), diagnostics)


class CamelotStreamAdapter(CamelotAdapter):
    def __init__(self):
        super().__init__('stream')


class CamelotLatticeAdapter(CamelotAdapter):
    def __init__(self):
        super().__init__('lattice')
