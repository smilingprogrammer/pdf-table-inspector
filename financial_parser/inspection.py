"""Read-only inspection helpers. This module has no Streamlit dependency."""
from dataclasses import dataclass
from decimal import Decimal
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile,ZIP_DEFLATED
import pdfplumber
from .pipeline import parse
from .exports import export_report,json_value
from .cell_exports import long_cells


@dataclass
class InspectionBundle:
    filename: str
    source: bytes
    report: dict
    files: dict[str,bytes]


def inspect_pdf(source,filename,config):
    filename=Path(filename).name or 'document.pdf'
    with TemporaryDirectory(prefix='pdf-inspector-') as tmp:
        root=Path(tmp)
        path=root/'source.pdf'
        path.write_bytes(source)
        destination=root/'exports'
        report=parse(path,destination,config)
        # Export a useful display name rather than a discarded temporary path.
        report['source']=filename
        export_report(report,destination)
        files={str(p.relative_to(destination)):p.read_bytes() for p in destination.rglob('*') if p.is_file()}
    return InspectionBundle(filename,source,report,files)


def full_table_region(table):
    boxes=[table['bbox']]+[item['bbox'] for item in table.get('headers',{}).get('items',[])]
    return [min(b[0] for b in boxes),min(b[1] for b in boxes),
            max(b[2] for b in boxes),max(b[3] for b in boxes)]


def render_source(source,page_number,table=None):
    with pdfplumber.open(BytesIO(source)) as pdf:
        if not 1 <= page_number <= len(pdf.pages):
            raise IndexError(f'Page {page_number} does not exist in this PDF')
        image=pdf.pages[page_number-1].to_image(resolution=120)
        if table:
            image.draw_rect(full_table_region(table),fill=None,stroke='#b54c3d',stroke_width=3)
        output=BytesIO()
        image.save(output,format='PNG')
        return output.getvalue()


def inspection_records(page,table_id):
    return [{key:str(value) if isinstance(value,Decimal) else value for key,value in record.items()}
            for record in long_cells(page) if record['table_id']==table_id]


def zip_download(bundle):
    output=BytesIO()
    with ZipFile(output,'w',ZIP_DEFLATED) as archive:
        archive.writestr('source.pdf',bundle.source)
        for filename,data in bundle.files.items():
            archive.writestr(filename,data)
    return output.getvalue()
