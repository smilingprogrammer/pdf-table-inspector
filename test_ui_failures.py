import csv
from io import StringIO
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
from financial_parser import ParseConfig
from financial_parser.ui_service import extract_in_worker,WorkerCrashed,WorkerTimeout


class WorkerTests(unittest.TestCase):
    def test_actual_worker_result_contains_headers_and_reference_body(self):
        bundle=extract_in_worker(Path('samples/financial-sample.pdf').read_bytes(),'upload.pdf',ParseConfig(render=False))
        table=bundle.report['pages'][0]['tables'][0]
        reference=json.loads(Path('data/financial-sample.reference.json').read_text())
        rows=list(csv.reader(StringIO(bundle.files[table['csv']].decode('utf-8-sig'))))
        self.assertEqual(rows[:3],[['','',reference['headers']['unit']]]+reference['headers']['rows'])
        self.assertEqual(rows[3:],reference['body'])

    def test_crash_and_timeout_are_distinct(self):
        config=ParseConfig(render=False)
        with patch('financial_parser.ui_service.subprocess.run',return_value=subprocess.CompletedProcess([], -9,'','')):
            with self.assertRaises(WorkerCrashed): extract_in_worker(b'pdf','x.pdf',config)
        with patch('financial_parser.ui_service.subprocess.run',side_effect=subprocess.TimeoutExpired('worker',.01)):
            with self.assertRaises(WorkerTimeout): extract_in_worker(b'pdf','x.pdf',config,timeout=.01)


class Upload:
    def __init__(self,name):
        self.name=name+'.pdf'
        path=Path('samples/financial-sample.pdf') if name=='sample' else Path(f'tests/fixtures/{name}.pdf')
        self.data=path.read_bytes()
    def getvalue(self): return self.data


class UIStateTests(unittest.TestCase):
    def setUp(self):
        try:
            from streamlit.testing.v1 import AppTest
        except ImportError as exc: self.skipTest(f'Optional Streamlit unavailable: {exc}')
        self.AppTest=AppTest

    def app(self): return self.AppTest.from_file('streamlit_app.py',default_timeout=20).run()
    def button(self,app,label): return next(b for b in app.button if b.label==label)
    def downloads(self,app): return app.get('download_button')
    def sample(self,app):
        self.button(app,'Try sample PDF').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(self.downloads(app)),3)

    def test_settings_rerun_updates_values_and_invalid_page_hides_old_downloads(self):
        app=self.app();self.sample(app)
        old=app.session_state['bundle']
        app.selectbox(key='number_format').select('1,234.56').run()
        self.assertTrue(any('Settings changed' in m.value for m in app.info))
        self.assertEqual(app.session_state['parsed_config']['number_profile'],'auto')
        self.button(app,'Extract tables').click().run()
        self.assertEqual(app.session_state['parsed_config']['number_profile'],'comma-dot')
        values=app.dataframe[1].value
        self.assertEqual(values.loc[values['Original text']=='608,281','Parsed value'].iloc[0],'608281')
        app.text_input(key='pages').set_value('999').run()
        self.button(app,'Extract tables').click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any('requested page does not exist' in e.value for e in app.error))
        self.assertEqual(len(self.downloads(app)),0)
        self.assertEqual(len(app.dataframe),0)

    def test_failed_worker_reruns_clear_results_and_downloads_persistently(self):
        for error in [WorkerCrashed('worker crashed'),WorkerTimeout('worker timed out')]:
            with self.subTest(error=type(error).__name__):
                app=self.app();self.sample(app)
                with patch('financial_parser.ui_service.extract_in_worker',side_effect=error):
                    self.button(app,'Extract tables').click().run()
                self.assertFalse(app.exception)
                self.assertEqual(len(self.downloads(app)),0)
                self.assertEqual(len(app.dataframe),0)
                self.assertTrue(any(str(error) in e.value for e in app.error))
                app.run()
                self.assertEqual(len(self.downloads(app)),0)
                self.assertEqual(len(app.dataframe),0)
                self.assertTrue(any(str(error) in e.value for e in app.error))
                self.button(app,'Extract tables').click().run()
                self.assertFalse(app.exception)
                self.assertEqual(len(self.downloads(app)),3)
                self.assertEqual(len(app.error),0)

    def test_missing_sample_file_hides_previous_result(self):
        app=self.app();self.sample(app)
        with patch('financial_parser.ui_service.SAMPLE_PATH',Path('/private/tmp/no-such-pdf-inspector-sample.pdf')):
            self.button(app,'Try sample PDF').click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any('sample PDF is missing' in e.value for e in app.error))
        self.assertEqual(len(self.downloads(app)),0)
        self.assertEqual(len(app.dataframe),0)

    def test_switch_uploads_and_clear_upload(self):
        app=self.app()
        # AppTest does not implement file uploads: mock only that widget boundary.
        # Actual browser upload/download is verified separately.
        with patch('streamlit.file_uploader',return_value=Upload('sample')):
            app.run()
            self.button(app,'Extract tables').click().run()
            self.assertFalse(app.exception)
            reference=json.loads(Path('data/financial-sample.reference.json').read_text())
            expected=[['','',reference['headers']['unit']]]+reference['headers']['rows']+reference['body']
            self.assertEqual(app.dataframe[0].value.values.tolist(),expected)
            old_hash=app.session_state['bundle'].report['source_sha256']
        with patch('streamlit.file_uploader',return_value=Upload('four-column')):
            app.run()
            self.assertEqual(len(self.downloads(app)),0)
            self.assertEqual(len(app.dataframe),0)
            self.button(app,'Extract tables').click().run()
            self.assertFalse(app.exception)
            self.assertNotEqual(app.session_state['bundle'].report['source_sha256'],old_hash)
            self.assertEqual(len(app.dataframe[0].value.columns),4)
        app.run()
        self.assertEqual(len(self.downloads(app)),0)
        self.assertTrue(any(m.value=='Start with a PDF' for m in app.subheader))

    def test_same_bytes_with_new_filename_is_a_new_upload(self):
        app=self.app()
        first=Upload('sample')
        with patch('streamlit.file_uploader',return_value=first):
            app.run()
            self.button(app,'Extract tables').click().run()
            original_hash=app.session_state['bundle'].report['source_sha256']
        renamed=Upload('sample');renamed.name='renamed-sample.pdf'
        with patch('streamlit.file_uploader',return_value=renamed):
            app.run()
            self.assertEqual(len(self.downloads(app)),0)
            self.button(app,'Extract tables').click().run()
            self.assertEqual(app.session_state['bundle'].filename,'renamed-sample.pdf')
            self.assertEqual(app.session_state['bundle'].report['source_sha256'],original_hash)
