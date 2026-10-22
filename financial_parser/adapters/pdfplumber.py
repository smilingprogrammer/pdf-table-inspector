import pdfplumber
from table_models import candidate_from_pdfplumber
from .base import AdapterResult, PageInput
from ..config import ParseConfig


class PdfplumberAdapter:
    def __init__(self, strategy='lines'):
        if strategy not in ('lines', 'text'):
            raise ValueError('Unsupported strategy')
        self.strategy = strategy
        self.name = f'pdfplumber-{strategy}'

    def extract(self, page: PageInput, config: ParseConfig) -> AdapterResult:
        settings = {'vertical_strategy': self.strategy, 'horizontal_strategy': self.strategy,
                    **config.engine_settings}
        with pdfplumber.open(page.source) as pdf:
            native = pdf.pages[page.page - 1]
            tables = tuple(candidate_from_pdfplumber(
                table, f'{page.document_id}:{self.name}', page.page, index,
                f'page-{page.page:03d}-table-{index:02d}.csv')
                for index, table in enumerate(native.find_tables(settings), 1))
            finder = native.debug_tablefinder(settings)
            return AdapterResult(tables, {
                'version': pdfplumber.__version__, 'settings': settings,
                'edges': [{k: edge[k] for k in ('x0', 'top', 'x1', 'bottom')}
                          for edge in finder.edges],
            })
