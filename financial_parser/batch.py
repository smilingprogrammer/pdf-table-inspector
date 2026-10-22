"""Document-isolated batch processing; one failed document never hides later ones."""
from pathlib import Path
import json
from .pipeline import parse
from .exports import json_value
from .config import ParseConfig
from dataclasses import asdict


def parse_batch(sources,destination,config=None):
    config=config or ParseConfig()
    destination=Path(destination)
    destination.mkdir(parents=True,exist_ok=True)
    documents=[]
    for index,source in enumerate(sources,1):
        source=Path(source)
        directory=destination/f'{index:03d}-{source.stem}'
        try:
            result=parse(source,directory,config)
            documents.append({'source':str(source),'status':result['status'],
                              'source_sha256':result.get('source_sha256'),
                              'errors':result['errors']+[{'page':p['page'],**e} for p in result['pages'] for e in p['errors']],
                              'report':str(directory/'report.json'),'result':result})
        except Exception as exc:
            documents.append({'source':str(source),'source_sha256':None,'status':'failed',
                              'errors':[{'type':type(exc).__name__,'message':str(exc)}]})
    summary={'config':asdict(config),'documents':documents,'status':'complete' if all(d['status']=='complete' for d in documents) else 'partial'}
    (destination/'batch.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=json_value),encoding='utf-8')
    return summary
