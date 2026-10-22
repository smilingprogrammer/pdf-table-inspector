"""UI file loading and bounded worker execution; no Streamlit imports."""
from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile,BadZipFile
from .inspection import InspectionBundle

ROOT=Path(__file__).resolve().parents[1]
SAMPLE_PATH=ROOT/'samples/financial-sample.pdf'


class WorkerCrashed(RuntimeError): pass
class WorkerTimeout(TimeoutError): pass


def read_sample():
    return SAMPLE_PATH.name,SAMPLE_PATH.read_bytes()


def extract_in_worker(source,filename,config,timeout=45):
    with TemporaryDirectory(prefix='pdf-ui-worker-') as tmp:
        root=Path(tmp)
        (root/'source.pdf').write_bytes(source)
        (root/'config.json').write_text(json.dumps(asdict(config)))
        command=[sys.executable,'-m','financial_parser.inspection_worker',str(root/'source.pdf'),
                 str(root/'config.json'),str(root/'result.zip'),Path(filename).name]
        try:
            result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise WorkerTimeout(f'Extraction timed out after {timeout:g} seconds. Try fewer pages or a different method.') from exc
        if result.returncode!=0:
            raise WorkerCrashed(f'Extraction worker stopped unexpectedly (exit {result.returncode}). Try another method or document.')
        try:
            with ZipFile(root/'result.zip') as archive:
                files={name:archive.read(name) for name in archive.namelist() if name!='source.pdf'}
            report=json.loads(files['report.json'])
        except (OSError,ValueError,KeyError,BadZipFile) as exc:
            raise WorkerCrashed('Extraction worker did not return a readable result.') from exc
        return InspectionBundle(Path(filename).name,source,report,files)
