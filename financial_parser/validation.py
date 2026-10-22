"""Structural diagnostics only: never interpret accounting relationships."""
import math


def validate(tables, page_number, size):
    issues=[]
    ids=set()
    def issue(entity,code,message,**details):
        issues.append({'id':entity,'code':code,'message':message,**details})
    def integer(value):
        return isinstance(value,int) and not isinstance(value,bool)
    def box_ok(box):
        try:
            return (len(box)==4 and all(isinstance(x,(int,float)) and math.isfinite(x) for x in box)
                    and 0<=box[0]<box[2]<=size[0] and 0<=box[1]<box[3]<=size[1])
        except (TypeError,IndexError):
            return False
    for table in tables:
        if table.id in ids: issue(table.id,'duplicate_id','Duplicate ID')
        ids.add(table.id)
        valid_table_box=box_ok(table.bbox)
        if table.page!=page_number or not valid_table_box:
            issue(table.id,'invalid_table_bounds','Invalid page or table bounding box')
        if not all(integer(v) and v>0 for v in (table.row_count,table.column_count)):
            issue(table.id,'invalid_dimensions','Grid dimensions must be positive integers')
            continue
        occupied={}
        boundaries={'x':{},'y':{}}
        valid_boxes=[]
        for cell in table.cells:
            if cell.id in ids: issue(cell.id,'duplicate_id','Duplicate ID')
            ids.add(cell.id)
            if (not all(integer(v) for v in (cell.row,cell.column,cell.row_span,cell.column_span))
                or cell.row<0 or cell.column<0 or cell.row_span<1 or cell.column_span<1
                or cell.row+cell.row_span>table.row_count
                or cell.column+cell.column_span>table.column_count):
                issue(cell.id,'invalid_span','Invalid cell position or span')
                continue
            if cell.bbox is None:
                issue(cell.id,'missing_cell_bounds','Missing detector cell or text cell without bounds',
                      row=cell.row,column=cell.column,raw_text=cell.raw_text)
            elif not box_ok(cell.bbox):
                issue(cell.id,'invalid_cell_bounds','Invalid cell bounding box')
            else:
                box=cell.bbox
                if valid_table_box and not (table.bbox[0]<=box[0]<box[2]<=table.bbox[2]
                                            and table.bbox[1]<=box[1]<box[3]<=table.bbox[3]):
                    issue(cell.id,'cell_outside_table','Cell bounding box outside table')
                for axis,index,value in [('x',cell.column,box[0]),('x',cell.column+cell.column_span,box[2]),
                                         ('y',cell.row,box[1]),('y',cell.row+cell.row_span,box[3])]:
                    prior=boundaries[axis].get(index)
                    if prior is not None and abs(prior-value)>1e-5:
                        issue(cell.id,'grid_geometry_mismatch','Bounding box disagrees with logical grid boundary',
                              axis=axis,boundary=index,expected=prior,actual=value)
                    boundaries[axis].setdefault(index,value)
                for other in valid_boxes:
                    overlap_x=min(box[2],other.bbox[2])-max(box[0],other.bbox[0])
                    overlap_y=min(box[3],other.bbox[3])-max(box[1],other.bbox[1])
                    if overlap_x>1e-5 and overlap_y>1e-5:
                        issue(cell.id,'geometric_overlap','Cell boxes overlap',other_cell_id=other.id)
                valid_boxes.append(cell)
            slots={(r,c) for r in range(cell.row,cell.row+cell.row_span)
                   for c in range(cell.column,cell.column+cell.column_span)}
            duplicates=sorted(slot for slot in slots if slot in occupied)
            if duplicates:
                issue(cell.id,'overlapping_spans','Overlapping logical cell spans',positions=duplicates)
            for slot in slots: occupied.setdefault(slot,cell.id)
        missing=sorted((r,c) for r in range(table.row_count) for c in range(table.column_count)
                       if (r,c) not in occupied)
        if missing:
            issue(table.id,'missing_grid_positions','Unrepresented grid positions',positions=missing)
    return issues
