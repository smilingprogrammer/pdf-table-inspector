"""Run an unmodified dcavacec/pdf-parse checkout against our visual reference."""
import argparse
import contextlib
import importlib.metadata
import io
import json
import logging
from pathlib import Path
import subprocess
import sys

cli = argparse.ArgumentParser(description=__doc__)
cli.add_argument('checkout', type=Path)
args = cli.parse_args()
sys.path.insert(0, str(args.checkout.resolve()))
from pdf_parse import PDFParser
from pdf_table_extractor import PDFTableExtractor

source = Path('samples/financial-sample.pdf').resolve()
out = Path('output/repository-review')
out.mkdir(parents=True, exist_ok=True)
reference = json.loads(Path('data/financial-sample.reference.json').read_text())
report = {'commit': subprocess.check_output(['git','rev-parse','HEAD'], cwd=args.checkout, text=True).strip(),
          'versions': {p: importlib.metadata.version(p) for p in ['pypdf','pdfplumber','pandas','camelot-py','tabula-py']},
          'runs': {}}
for method in ['PDFParser', 'pdfplumber', 'camelot', 'tabula', 'auto']:
    capture = io.StringIO()
    handler = logging.StreamHandler(capture)
    logging.getLogger().addHandler(handler)
    result = {}
    try:
        with contextlib.redirect_stdout(capture), contextlib.redirect_stderr(capture):
            if method == 'PDFParser':
                tables = PDFParser().parse_pdf(source)
                result['tables'] = [t.to_dict() for t in tables]
            else:
                extractor = PDFTableExtractor()
                frames = extractor.extract_tables_from_pdf(source, method=method)
                result['enabled_methods'] = extractor.extraction_methods
                result['tables'] = [{'shape': list(df.shape), 'columns': list(df.columns),
                                     'rows': df.values.tolist()} for df in frames]
                for i, df in enumerate(frames, 1):
                    df.to_csv(out / f'{method}-{i}.csv', index=False)
            result['table_count'] = len(result['tables'])
    except Exception as exc:
        result['error'] = {'type':type(exc).__name__, 'message':str(exc)}
    finally:
        logging.getLogger().removeHandler(handler)
    result['log'] = capture.getvalue()
    report['runs'][method] = result
    print(method, result.get('table_count'), result.get('error', ''), flush=True)

# Probe the actual upstream de-duplication method on two separate occurrences.
import pandas as pd
frame = pd.DataFrame([['same','1'],['same','2']])
report['dedup_probe'] = {'input_occurrences': 2,
    'output_occurrences': len(PDFTableExtractor()._remove_duplicate_tables([frame,frame.copy()])),
    'note': 'Synthetic probe: equal content in separate occurrences has no page/geometry distinction.'}
(out / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
