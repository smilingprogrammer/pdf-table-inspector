import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from financial_parser import ParseConfig, parse
from financial_parser.adapters import AdapterResult
from table_models import Cell, TableCandidate


class PipelineTests(unittest.TestCase):
    def test_replacement_engine_failure_empty_success_and_export_error(self):
        class Replacement:
            name = 'replacement'
            def extract(self, page, config):
                if page.page == 1:
                    raise RuntimeError('engine failed on page one')
                if page.page == 2:
                    return AdapterResult()
                return AdapterResult((TableCandidate(
                    't3', 3, (0,0,10,10), 1, 1,
                    (Cell('c3', 'first', 0,0,1,1,(0,0,10,10)),), 'third.csv'),))

        class Document:
            pages = [SimpleNamespace(width=10, height=10)] * 3
            def __enter__(self): return self
            def __exit__(self, *args): pass

        def context(page, config):
            return {'text': 'some text', 'text_status': 'text_candidate'}

        def exports(page, entry, tables, diagnostics, destination, config, record_error):
            if entry['page'] == 3:
                record_error('render_source', OSError('render failed'))

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'source.pdf'
            source.write_bytes(b'test input')
            with patch('financial_parser.pipeline.pdfplumber.open', return_value=Document()), \
                 patch('financial_parser.pipeline.extract_context', side_effect=context), \
                 patch('financial_parser.pipeline.outside_text', return_value=''), \
                 patch('financial_parser.pipeline.attach_headers', return_value={}), \
                 patch('financial_parser.pipeline.export_page', side_effect=exports):
                result = parse(source, Path(tmp)/'out', ParseConfig(), adapter=Replacement())
            self.assertEqual([p['engine_run']['status'] for p in result['pages']],
                             ['failed', 'no_tables', 'success'])
            self.assertEqual(result['pages'][0]['errors'][0]['message'], 'engine failed on page one')
            self.assertEqual(result['pages'][2]['tables'][0]['cells'][0]['raw_text'], 'first')
            self.assertEqual(result['pages'][2]['errors'][0]['stage'], 'render_source')
            self.assertEqual(json.loads((Path(tmp)/'out/report.json').read_text())['engine'], 'replacement')
            self.assertEqual(result['status'], 'partial')

    def test_real_sample_regression(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = parse('samples/financial-sample.pdf', tmp, ParseConfig(render=False))
            page = result['pages'][0]
            self.assertEqual(page['engine_run']['status'], 'success')
            self.assertEqual(page['validation'], [])
            self.assertEqual(page['errors'], [])
            self.assertEqual(page['tables'][0]['dimensions'], {'rows':43, 'columns':3})
            self.assertEqual(page['tables'][0]['rows'][0], ['資産の部','',''])
            from evaluate import evaluate
            reference = json.loads(Path('data/financial-sample.reference.json').read_text())
            score = evaluate(reference, result)
            self.assertEqual(score['body']['passed'],129)
            self.assertEqual(score['headers']['passed'],7)


if __name__ == '__main__':
    unittest.main()


class OptionalCamelotTests(unittest.TestCase):
    def test_original_strings_coordinates_and_headers(self):
        try:
            import camelot
        except ImportError:
            self.skipTest('Install requirements.txt for Camelot integration test')
        with tempfile.TemporaryDirectory() as tmp:
            result = parse('samples/financial-sample.pdf', tmp,
                           ParseConfig(engine='camelot-stream', render=False))
            page = result['pages'][0]
            self.assertEqual(page['errors'], [])
            self.assertEqual(page['validation'], [])
            table = page['tables'][0]
            self.assertEqual(table['dimensions'], {'rows':45,'columns':3})
            self.assertEqual(table['cells'][1]['raw_text'], '前連結会計年度 \n')
            self.assertIn('資産の部', table['rows'][2][0])
            self.assertAlmostEqual(table['cells'][1]['bbox'][1],121.12452)
            self.assertEqual(len({c['id'] for c in table['cells']}),135)
            reference = json.loads(Path('data/financial-sample.reference.json').read_text())
            # Explicit derived view for this test; canonical raw text is unchanged.
            self.assertEqual([[v.strip() for v in row] for row in table['rows'][2:]],
                             reference['body'])
