"""Build an allowlisted, standalone Streamlit source bundle."""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[1]


def build(destination):
    destination=Path(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    names=['streamlit_app.py','parse_pdf.py','table_models.py','evaluate.py','check_accounting.py',
           'DEPLOYMENT.md','deploy/app.py','requirements.txt','scripts/package_streamlit.py','.gitignore','.streamlit/config.toml','ui/tokens.css','samples/financial-sample.pdf']
    names += [str(p.relative_to(ROOT)) for p in sorted((ROOT/'financial_parser').glob('*.py'))]
    names += [str(p.relative_to(ROOT)) for p in sorted((ROOT/'financial_parser/adapters').glob('*.py'))]
    names += [str(p.relative_to(ROOT)) for p in sorted((ROOT/'data').glob('*.json'))]
    files={name:(ROOT/name).read_bytes() for name in names}
    files['README.md']=b'# PDF table inspector\n\nSee DEPLOYMENT.md. Standalone entry point: streamlit_app.py. Python 3.12.\n'
    manifest={'python':'3.12','entrypoint':'streamlit_app.py',
              'files':{name:hashlib.sha256(data).hexdigest() for name,data in sorted(files.items())}}
    files['manifest.json']=(json.dumps(manifest,indent=2)+'\n').encode()
    with ZipFile(destination,'w',ZIP_DEFLATED) as archive:
        for name,data in sorted(files.items()):
            archive.writestr('pdf-table-inspector/'+name,data)
    checksum=hashlib.sha256(destination.read_bytes()).hexdigest()
    destination.with_suffix('.zip.sha256').write_text(f'{checksum}  {destination.name}\n')
    return manifest


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--out',type=Path,default=ROOT/'dist/pdf-table-inspector-streamlit.zip')
    args=cli.parse_args()
    manifest=build(args.out)
    print(f'{args.out}: {len(manifest["files"])} files plus manifest')
