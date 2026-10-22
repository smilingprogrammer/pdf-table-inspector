from .base import AdapterResult, PageInput, TableAdapter
from .pdfplumber import PdfplumberAdapter
from .camelot import CamelotStreamAdapter, CamelotLatticeAdapter

ADAPTERS = {'camelot-stream': CamelotStreamAdapter, 'camelot-lattice': CamelotLatticeAdapter,
            'pdfplumber-lines': lambda: PdfplumberAdapter('lines'),
            'pdfplumber-text': lambda: PdfplumberAdapter('text')}


def get_adapter(name):
    try:
        return ADAPTERS[name]()
    except KeyError:
        raise ValueError(f'Unknown engine: {name}') from None
