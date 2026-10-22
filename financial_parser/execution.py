"""Run configured engines with explicit attempt histories."""
from dataclasses import replace
from .adapters import get_adapter
from .ranking import rank_and_associate
from .validation import validate


def execute(page_input, config, characters, size, record_error, adapter=None):
    multi = config.engine in ('auto','compare') and adapter is None
    names = config.engines if multi else (config.engine,)
    if config.engine=='auto' and multi:
        names = ('pdfplumber-lines',)+tuple(n for n in names if n!='pdfplumber-lines')
    tables=[]
    runs=[]
    provenance={}
    stopped=False
    for name in names:
        if stopped:
            runs.append({'engine':name,'status':'not_run','table_count':0,'reason':'auto_candidate_passed_heuristics'})
            continue
        run={'engine':name,'status':'failed','table_count':0}
        runs.append(run)
        try:
            engine = adapter if adapter is not None else get_adapter(name)
            run['engine'] = engine.name
            engine_config=replace(config,engine=name,
                engine_settings=config.settings_by_engine.get(name,config.engine_settings))
            output=engine.extract(page_input,engine_config)
            candidates=tuple(replace(t,csv=f'{engine.name}-{t.csv}') for t in output.tables) if multi else output.tables
            runs[-1].update(status='success' if candidates else 'no_tables',
                            table_count=len(candidates),diagnostics=output.diagnostics)
            tables.extend(candidates)
            provenance.update({t.id:engine.name for t in candidates})
            if config.engine=='auto' and multi:
                ranked=rank_and_associate(candidates,characters,config)
                issues=validate(candidates,page_input.page,size)
                stopped=bool(candidates) and not issues and all(
                    not m['possible_failure'] for m in ranked['measurements'].values())
        except Exception as exc:
            if isinstance(exc, ImportError):
                run['status']='unavailable'
            run['error']={'type':type(exc).__name__,'message':str(exc)}
            record_error('adapter',exc,run['engine'])
    ranking=rank_and_associate(tables,characters,config)
    ranking['candidate_engines']=provenance
    ranking['decision']='auto_stopped_on_heuristics' if stopped else 'all_configured_routes_attempted'
    return tuple(tables),runs,ranking
