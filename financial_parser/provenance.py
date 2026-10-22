"""Installed distribution versions, distinct from per-page execution outcomes."""
from importlib.metadata import version,PackageNotFoundError


def engine_versions(names):
    result={}
    for name in names:
        package='camelot-py' if name.startswith('camelot-') else 'pdfplumber' if name.startswith('pdfplumber-') else None
        if package is None:
            result[name]={'package':None,'version':None,'dependency_status':'unknown'}
            continue
        try:
            result[name]={'package':package,'version':version(package),'dependency_status':'installed'}
        except PackageNotFoundError:
            result[name]={'package':package,'version':None,'dependency_status':'unavailable'}
    return result
