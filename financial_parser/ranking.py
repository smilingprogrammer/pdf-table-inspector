"""Inspectable geometric heuristics, never a guarantee of column correctness."""
from collections import Counter


def area(box):
    return max(0,box[2]-box[0])*max(0,box[3]-box[1])


def overlap(a,b):
    intersection = area((max(a[0],b[0]),max(a[1],b[1]),min(a[2],b[2]),min(a[3],b[3])))
    return {'intersection_over_union':intersection / max(area(a)+area(b)-intersection,1e-12),
            'intersection_over_smaller':intersection / max(min(area(a),area(b)),1e-12)}


def contains(box,char):
    return box[0] <= (char['x0']+char['x1'])/2 < box[2] and box[1] <= (char['top']+char['bottom'])/2 < box[3]


def counts(text):
    return Counter(c for c in (text or '') if not c.isspace())


def measure(table, characters):
    region = [c for c in characters if not c['text'].isspace() and contains(table.bbox,c)]
    source_count = sum(sum(counts(c['text']).values()) for c in region)
    covered = 0
    ambiguous = 0
    for char in region:
        owners = sum(contains(c.bbox,char) for c in table.cells if c.bbox)
        weight = sum(counts(char['text']).values())
        covered += weight if owners else 0
        ambiguous += weight if owners > 1 else 0
    matches = 0
    extracted_count = 0
    source_text = Counter()
    emitted_text = Counter()
    cell_measurements = []
    for char in region:
        source_text.update(counts(char['text']))
    for cell in table.cells:
        emitted = counts(cell.raw_text)
        emitted_text.update(emitted)
        extracted_count += sum(emitted.values())
        source = Counter()
        if cell.bbox:
            for char in region:
                if contains(cell.bbox,char): source.update(counts(char['text']))
        matched = sum((emitted & source).values())
        matches += matched
        cell_measurements.append({'cell_id':cell.id,
            'source_character_count':sum(source.values()),
            'extracted_character_count':sum(emitted.values()),
            'matched_character_count':matched,
            'spatial_character_agreement':matched/max(sum(source.values()),sum(emitted.values()),1)})
    density = sum(bool(counts(c.raw_text)) for c in table.cells) / max(len(table.cells),1)
    coverage = covered/source_count if source_count else 0
    text_coverage = sum((source_text & emitted_text).values())/source_count if source_count else 0
    agreement = matches/max(source_count,extracted_count,1)
    return {'source_character_count_in_region':source_count,
            'source_characters_covered':covered, 'source_character_coverage':coverage,
            'source_text_character_coverage':text_coverage,
            'extracted_character_count':extracted_count, 'spatially_matched_characters':matches,
            'spatial_character_agreement':agreement, 'ambiguous_source_characters':ambiguous,
            'cell_measurements':cell_measurements,
            'nonempty_cells':sum(bool(counts(c.raw_text)) for c in table.cells),
            'cell_count':len(table.cells), 'nonempty_cell_density':density,
            'score_kind':'heuristic_not_correctness_probability',
            'score':0.5*text_coverage+0.25*density+0.25*agreement}


def grid_differs(a,b,tolerance):
    if (a.row_count,a.column_count)!=(b.row_count,b.column_count): return True
    for axis in ((0,2),(1,3)):
        left = {c.bbox[i] for c in a.cells if c.bbox for i in axis}
        right = {c.bbox[i] for c in b.cells if c.bbox for i in axis}
        if any(min((abs(x-y) for y in right),default=float('inf'))>tolerance for x in left): return True
        if any(min((abs(x-y) for y in left),default=float('inf'))>tolerance for x in right): return True
    return False


def rank_and_associate(tables, characters, config):
    metrics = {t.id:measure(t,characters) for t in tables}
    parents = list(range(len(tables)))
    def root(i):
        while parents[i]!=i:
            i=parents[i]
        return i
    links = []
    conflicts = set()
    for i,a in enumerate(tables):
        for j in range(i+1,len(tables)):
            b=tables[j]
            geometry=overlap(a.bbox,b.bbox)
            if geometry['intersection_over_smaller'] < config.overlap_threshold: continue
            parents[root(j)]=root(i)
            different=grid_differs(a,b,config.grid_tolerance_points)
            links.append({'a':a.id,'b':b.id,**geometry,'different_grid':different})
            if different: conflicts.update((a.id,b.id))
    groups={}
    for i,t in enumerate(tables): groups.setdefault(root(i),[]).append(t.id)
    result=[]
    for ids in groups.values():
        ordered=sorted(ids,key=lambda identity: (-metrics[identity]['score'],identity))
        result.append({'candidate_ids':ids,'ranked_candidate_ids':ordered,
                       'preferred_candidate_id':ordered[0],
                       'different_grids':any(i in conflicts for i in ids),
                       'requires_review':True})
    for identity,m in metrics.items():
        reasons=[]
        if not m['source_character_count_in_region']: reasons.append('no_source_character_evidence')
        if m['source_character_coverage']<config.min_source_coverage: reasons.append('low_source_character_coverage')
        if m['source_text_character_coverage']<config.min_source_coverage: reasons.append('missing_source_characters_in_text')
        if m['spatial_character_agreement']<config.min_spatial_agreement: reasons.append('cell_text_geometry_disagreement')
        if m['nonempty_cell_density']<config.min_cell_density: reasons.append('low_nonempty_cell_density')
        if m['ambiguous_source_characters']: reasons.append('ambiguous_character_ownership')
        if identity in conflicts: reasons.append('overlapping_candidate_has_different_grid')
        m.update(possible_failure=bool(reasons),flags=reasons,requires_review=True)
    return {'measurements':metrics,'overlap_links':links,'groups':result,
            'score_definition':{'kind':'heuristic_not_correctness_probability',
                'weights':{'source_text_character_coverage':0.5,'nonempty_cell_density':0.25,
                           'spatial_character_agreement':0.25}},
            'limitations':['Coverage is measured inside each candidate region, not against an unknown true table extent.',
                          'Spatial agreement compares characters within cell boxes; it does not certify year/account assignment or character order.',
                          'Preferred candidate is a heuristic ranking, not an accepted financial table.']}
