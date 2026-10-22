"""Optional read-only UI. Start with: streamlit run streamlit_app.py"""
import hashlib
from dataclasses import asdict
from pathlib import Path
import pandas as pd
import streamlit as st
from financial_parser import ParseConfig
from financial_parser.cli import pages_argument
from financial_parser.inspection import render_source,inspection_records,zip_download
from financial_parser.ui_service import extract_in_worker,read_sample

ROOT=Path(__file__).resolve().parent
ENGINES={'Automatic':'auto','Compare all methods':'compare','Ruled tables':'pdfplumber-lines',
         'Borderless tables':'pdfplumber-text','Camelot stream (optional)':'camelot-stream',
         'Camelot lattice (optional)':'camelot-lattice'}
FORMATS={'Automatic — leave ambiguous values unresolved':'auto','1,234.56':'comma-dot',
         '1.234,56':'dot-comma','1 234.56':'space-dot','1 234,56':'space-comma'}
ENGINE_LABELS={v:k for k,v in ENGINES.items()}


def main():
    st.set_page_config(page_title='PDF table inspector',layout='wide')
    st.markdown('<style>'+(ROOT/'ui/tokens.css').read_text()+'</style>',unsafe_allow_html=True)
    st.title('PDF table inspector')
    st.caption('Compare the page with its extracted values. Read-only inspection and downloads.')
    with st.sidebar:
        st.header('Document')
        uploaded=st.file_uploader('Upload a PDF',type=['pdf'],key='upload')
        sample=st.button('Try sample PDF',width='stretch')
        if uploaded:
            incoming=uploaded.getvalue()
            signature=(uploaded.name,hashlib.sha256(incoming).hexdigest())
            if signature!=st.session_state.get('upload_seen'):
                st.session_state['source']=(uploaded.name,incoming)
                st.session_state['source_kind']='upload'
                st.session_state['upload_seen']=signature
                st.session_state.pop('run_error',None)
                st.session_state.pop('bundle',None)
        elif st.session_state.get('upload_seen') is not None:
            st.session_state.pop('upload_seen',None)
            if st.session_state.get('source_kind')=='upload':
                st.session_state.pop('source',None)
                st.session_state.pop('bundle',None)
        if sample:
            st.session_state.pop('bundle',None)
            st.session_state.pop('parsed_config',None)
            st.session_state.pop('run_error',None)
            try:
                st.session_state['source']=read_sample()
                st.session_state['source_kind']='sample'
            except OSError:
                st.session_state.pop('source',None)
                st.session_state['run_error']='The sample PDF is missing or unreadable. Upload a PDF to continue.'
        source=st.session_state.get('source')
        if source: st.caption(source[0])
        st.subheader('Settings')
        method=st.selectbox('Extraction method',list(ENGINES),key='method')
        number_format=st.selectbox('Number format',list(FORMATS),key='number_format')
        pages=st.text_input('Pages',placeholder='All pages, or 1,3-5',key='pages')
        st.caption('Automatic keeps unclear separators unresolved. No OCR is run.')
        extract=st.button('Extract tables',type='primary',disabled=source is None,width='stretch')
    try:
        page_selection=pages_argument([pages]) if pages.strip() else None
        config=ParseConfig(engine=ENGINES[method],number_profile=FORMATS[number_format],pages=page_selection,render=False)
    except ValueError:
        st.error('Use page numbers or ascending ranges, for example 1,3-5.')
        return
    if st.session_state.get('run_error') and (source is None or not (extract or sample)):
        st.error(st.session_state['run_error'])
    if source is None:
        st.subheader('Start with a PDF')
        st.write('Upload a financial PDF in the sidebar, or try the Japanese sample. Then extract tables to compare the source with each candidate.')
        st.info('Your workspace will show the page on the left and the extracted table on the right. Original text is kept alongside parsed values.')
        return
    if extract or sample:
        st.session_state.pop('bundle',None)
        st.session_state.pop('parsed_config',None)
        st.session_state.pop('run_error',None)
        with st.spinner('Reading pages and finding tables…'):
            try:
                st.session_state['bundle']=extract_in_worker(source[1],source[0],config)
                st.session_state['parsed_config']=asdict(config)
            except Exception as exc:
                st.session_state['run_error']=f'This PDF could not be processed: {exc}'
                st.error(st.session_state['run_error'])
                return
    bundle=st.session_state.get('bundle')
    if bundle is None:
        if st.session_state.get('run_error'): return
        st.info('Document ready. Choose your settings, then select Extract tables.')
        return
    if asdict(config)!=st.session_state.get('parsed_config'):
        st.info('Settings changed. Select Extract tables to update these results.')
    report=bundle.report
    for error in report['errors']:
        st.error(f"Could not read this document: {error['message']}")
    pages_result=report['pages']
    if not pages_result:
        st.warning('No readable pages are available. Download the JSON report for details.')
        st.download_button('Download JSON',bundle.files['report.json'],'report.json','application/json')
        return
    page_labels=[f"Page {p['page']}" for p in pages_result]
    page_choice=st.selectbox('Page',page_labels,key='selected_page')
    page_index=page_labels.index(page_choice)
    page=pages_result[page_index]
    tables=page['tables']
    invalid_page=any(e['stage']=='load_page' for e in page['errors'])
    if invalid_page:
        st.error('The requested page does not exist or could not be loaded. Choose a valid page and extract again.')
        return
    candidate=None
    if tables:
        def candidate_label(i):
            table=tables[i]
            engine=page.get('ranking',{}).get('candidate_engines',{}).get(table['id'],page['engine_run']['engine'])
            return f"{i+1}. {ENGINE_LABELS.get(engine,engine)} · {table['row_count']} rows × {table['column_count']} columns"
        candidate_labels=[candidate_label(i) for i in range(len(tables))]
        choice=st.selectbox('Table candidate',candidate_labels,key=f"candidate_{report.get('source_sha256')}_{page_index}")
        index=candidate_labels.index(choice)
        candidate=tables[index]
    for warning in page.get('warnings',[]):
        if warning['code']=='ocr_required':
            st.warning('This page is a scan or image-only PDF. OCR is required and is not supported yet. The source page is still available to inspect.')
        else: st.warning(warning['message'])
    unavailable={r['engine'] for r in page.get('engine_runs',[]) if r['status']=='unavailable'}
    for error in page['errors']:
        if error.get('engine') not in unavailable:
            st.warning(f"Some results are unavailable: {error['message']}")
    for attempt in page.get('engine_runs',[]):
        if attempt['status']=='unavailable': st.warning(f"{attempt['engine']} is not installed. Other available methods still ran.")
    left,right=st.columns([1,1],gap='large')
    with left:
        st.subheader('Source page')
        try:
            st.image(render_source(bundle.source,page['page'],candidate),width='stretch')
            if candidate: st.caption('The outline includes the detected grid, attached headings, and unit caption.')
        except Exception as exc:
            st.error(f'The source page could not be displayed: {exc}')
    with right:
        st.subheader('Extracted table')
        if candidate is None:
            if page.get('text_status')!='review_for_ocr':
                st.info('No tables were detected on this page. Try Compare all methods or Borderless tables, or select another page.')
            else: st.info('No extracted table is available until this page has usable text.')
        else:
            table_tab,value_tab=st.tabs(['Table','Values'])
            with table_tab:
                rows=candidate.get('headers',{}).get('display_rows',candidate['rows'])
                st.dataframe(pd.DataFrame(rows,columns=[f'Column {i+1}' for i in range(candidate['column_count'])]),hide_index=True,width='stretch',height=520)
                st.caption('Original text. Blank cells and section labels are preserved.')
            with value_tab:
                records=inspection_records(page,candidate['id'])
                columns=['cell_kind','row','column','raw_text','number_status','number_value']
                st.dataframe(pd.DataFrame(records).reindex(columns=columns).rename(columns={
                    'cell_kind':'Type','row':'Row (0-based)','column':'Column (0-based)','raw_text':'Original text',
                    'number_status':'Parse status','number_value':'Parsed value'}),hide_index=True,width='stretch',height=520)
                st.caption('Ambiguous values stay unresolved. A dash, blank, zero, and triangle-marked zero remain distinct.')
            measurement=page.get('ranking',{}).get('measurements',{}).get(candidate['id'],{})
            if measurement.get('possible_failure') or page.get('validation'):
                st.warning('This candidate needs review. Its grid or placement differs from other evidence.')
            with st.expander('Cell details and diagnostics'):
                records=inspection_records(page,candidate['id'])
                if records:
                    cell_labels=[f"{i+1}. {r['cell_kind']} · row {r.get('row')} · column {r.get('column')} · {r['raw_text']!r}" for i,r in enumerate(records)]
                    cell_choice=st.selectbox('Cell',cell_labels,key=f"cell_{candidate['id']}")
                    record=records[cell_labels.index(cell_choice)]
                    st.json({'cell':record,'parsed':page.get('normalized_cells',{}).get(record['cell_id'])})
                st.caption('Ranking is a heuristic, not a correctness probability.')
                st.json({'candidate_id':candidate['id'],'ranking':measurement,'structure':page.get('structural_validation'),
                         'engine_attempts':page.get('engine_runs',[])})
        st.subheader('Download')
        downloads=st.columns(3)
        with downloads[0]:
            csv_name=candidate['csv'] if candidate else 'cells.csv'
            st.download_button('CSV',bundle.files.get(csv_name,b''),csv_name,'text/csv',width='stretch',on_click='ignore')
        with downloads[1]:
            st.download_button('JSON',bundle.files['report.json'],'report.json','application/json',width='stretch',on_click='ignore')
        with downloads[2]:
            st.download_button('ZIP',zip_download(bundle),'pdf-tables.zip','application/zip',width='stretch',on_click='ignore')
        st.caption('CSV contains the selected table. JSON and ZIP retain all candidates and diagnostics.')
    st.divider()
    st.caption('Read-only · No source or extracted values are edited.')


if __name__=='__main__': main()
