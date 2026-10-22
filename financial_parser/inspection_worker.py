"""Isolated UI extraction worker; core parsing has no UI dependency."""
import json
from pathlib import Path
import sys
from .config import ParseConfig
from .inspection import inspect_pdf,zip_download


def main():
    source,settings,destination,filename=sys.argv[1:]
    config=ParseConfig(**json.loads(Path(settings).read_text()))
    bundle=inspect_pdf(Path(source).read_bytes(),filename,config)
    Path(destination).write_bytes(zip_download(bundle))


if __name__=='__main__': main()
