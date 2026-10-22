"""Explicit financial relationships, independent of extraction and grid validation."""
from decimal import Decimal, localcontext
from .numbers import parse_number


def validate_relationships(spec):
    rows={r['id']:r for r in spec['rows']}
    if len(rows)!=len(spec['rows']) or len({r['index'] for r in spec['rows']})!=len(rows):
        raise ValueError('Relationship row IDs and positions must be unique')
    if len({r['id'] for r in spec['relationships']})!=len(spec['relationships']):
        raise ValueError('Relationship IDs must be unique')
    for relationship in spec['relationships']:
        target=rows[relationship['target']]
        terms=[rows[i] for i in relationship['terms']]
        roles=[r['role'] for r in terms]
        if len(set(relationship['terms']))!=len(terms) or relationship['target'] in relationship['terms']:
            raise ValueError('Repeated term or self-referencing total')
        if relationship['kind']=='net':
            if target['role']!='net' or sorted(roles)!=['depreciation','gross']:
                raise ValueError('Net checks require exactly gross plus signed depreciation')
        elif relationship['kind']=='subtotal':
            if target['role'] not in ('subtotal','total') or any(r not in ('asset','net','subtotal') for r in roles):
                raise ValueError('Subtotal terms must use net assets, never gross or depreciation')
        else:
            raise ValueError('Unknown relationship kind')
    return rows


def check_accounting(table, spec, *, structure_issues=()):
    rows=validate_relationships(spec)
    result={'relationship_profile':spec['name'],'table_id':table.get('id'),
            'status':'checked','checks':[],'discrepancies':[],
            'structure_issues':list(structure_issues),
            'notes':['Differences are displayed minus computed, in displayed units.',
                     'No values, reference cells or extraction rankings are changed.',
                     'This is an explicit sample relationship list, not an inferred accounting tree.']}
    if structure_issues:
        result.update(status='blocked_by_structure')
        return result
    values=table.get('rows',[])
    if [len(values),max((len(r) for r in values),default=0)]!=spec['dimensions'] or any(len(r)!=spec['dimensions'][1] for r in values):
        result.update(status='not_applicable',reason='Grid dimensions differ from explicit relationship profile')
        return result
    mismatches=[{'row_id':r['id'],'row':r['index'],'expected_label':r['expected_label'],
                 'actual_label':values[r['index']][0]} for r in spec['rows']
                if values[r['index']][0]!=r['expected_label']]
    if mismatches:
        result.update(status='not_applicable',reason='Positional label guards failed',label_mismatches=mismatches)
        return result
    cells={(c['row'],c['column']):c for c in table.get('cells',[])}
    def operand(row_id,column):
        row=rows[row_id]
        parsed=parse_number(values[row['index']][column],spec['number_profile'])
        value=parsed.value
        assumption=None
        if parsed.status=='dash' and spec['dash_policy']=='zero_for_arithmetic_only':
            value=Decimal(0)
            assumption='dash contributes zero for this relationship only'
        return {'row_id':row_id,'row':row['index'],'column':column,'role':row['role'],
                'cell_id':cells.get((row['index'],column),{}).get('id'),
                'raw_text':parsed.raw_text,'parse_status':parsed.status,'value':value,
                'assumption':assumption}
    for relationship in spec['relationships']:
        for column in spec['columns']:
            target=operand(relationship['target'],column['index'])
            terms=[operand(i,column['index']) for i in relationship['terms']]
            check={'relationship_id':relationship['id'],'kind':relationship['kind'],
                   'period':column['period'],'column':column['index'],
                   'target':target,'terms':terms}
            if any(o['value'] is None for o in [target,*terms]):
                check.update(status='unresolved',difference=None,reason='An operand is not a resolved number')
            elif relationship['kind']=='net' and any(o['value']>0 for o in terms if o['role']=='depreciation'):
                check.update(status='unresolved',difference=None,reason='Expected signed negative depreciation; sign not repaired')
            else:
                with localcontext() as context:
                    context.prec=max(28,sum(len(o['value'].as_tuple().digits)+abs(o['value'].as_tuple().exponent) for o in [target,*terms])+4)
                    computed=sum((o['value'] for o in terms),Decimal(0))
                    difference=target['value']-computed
                check.update(status='balanced' if difference==0 else 'difference',displayed=target['value'],
                             computed=computed,difference=difference)
            result['checks'].append(check)
    result['discrepancies']=[c for c in result['checks'] if c['status']=='difference']
    result['summary']={s:sum(c['status']==s for c in result['checks']) for s in ('balanced','difference','unresolved')}
    return result
