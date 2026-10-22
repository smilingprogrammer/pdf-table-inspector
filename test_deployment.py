import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile
from scripts.package_streamlit import build


class DeploymentTests(unittest.TestCase):
    def test_archive_contents_manifest_and_real_worker(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive=Path(tmp)/'app.zip'
            manifest=build(archive)
            with ZipFile(archive) as zipfile:
                for name in zipfile.namelist():
                    self.assertFalse(any(segment in name.split('/') for segment in ['__pycache__','output','tmp','.venv']))
                    self.assertNotIn('secrets.toml',name)
                zipfile.extractall(Path(tmp)/'unpacked')
            root=Path(tmp)/'unpacked/pdf-table-inspector'
            for name,digest in manifest['files'].items():
                self.assertEqual(hashlib.sha256((root/name).read_bytes()).hexdigest(),digest)
            expected=(root/'requirements.txt').read_text()
            self.assertIn('streamlit==1.50.0',expected)
            self.assertIn('camelot-py==1.0.9',expected)
            self.assertTrue((root/'financial_parser/inspection_worker.py').is_file())
            program='''
import json
from pathlib import Path
from financial_parser import ParseConfig
from financial_parser.ui_service import extract_in_worker
import financial_parser
assert Path(financial_parser.__file__).resolve().is_relative_to(Path.cwd())
source=Path('samples/financial-sample.pdf').read_bytes()
bundle=extract_in_worker(source,'sample.pdf',ParseConfig(render=False))
reference=json.loads(Path('data/financial-sample.reference.json').read_text())
table=bundle.report['pages'][0]['tables'][0]
assert table['rows']==reference['body']
assert table['headers']['rows']==reference['headers']['rows']
assert table['headers']['unit']==reference['headers']['unit']
print('Packaged worker: body 129/129, headers 7/7')
'''
            result=subprocess.run([sys.executable,'-c',program],cwd=root,capture_output=True,text=True,timeout=90)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_cloud_entrypoint_and_packaged_ui(self):
        try:
            from streamlit.testing.v1 import AppTest
        except ImportError as exc: self.skipTest(f'Optional Streamlit unavailable: {exc}')
        app=AppTest.from_file('deploy/app.py',default_timeout=60).run()
        self.assertFalse(app.exception)
        self.assertTrue(any(h.value=='Start with a PDF' for h in app.subheader))
        with tempfile.TemporaryDirectory() as tmp:
            archive=Path(tmp)/'app.zip';build(archive)
            with ZipFile(archive) as z: z.extractall(tmp)
            root=Path(tmp)/'pdf-table-inspector'
            program='''
from streamlit.testing.v1 import AppTest
app=AppTest.from_file('streamlit_app.py',default_timeout=60).run()
assert not app.exception
next(b for b in app.button if b.label=='Try sample PDF').click().run(timeout=60)
assert not app.exception
assert len(app.dataframe[0].value)==46
assert len(app.get('download_button'))==3
print('Packaged AppTest: sample and downloads pass')
'''
            result=subprocess.run([sys.executable,'-c',program],cwd=root,capture_output=True,text=True,timeout=90)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
