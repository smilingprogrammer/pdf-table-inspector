# dcavacec/pdf-parse review

Inspected and ran unmodified commit `e07c388424159c0c8b1c14c3af2ed745d41aeea4`.
Source: https://github.com/dcavacec/pdf-parse/tree/e07c388424159c0c8b1c14c3af2ed745d41aeea4
Sample: `samples/financial-sample.pdf`. Full outputs, runtime versions and captured
logs are in `output/repository-review/results.json`; CSVs sit alongside it.
These are actual runs, not mocked engines. Java 17 was available; Tabula used
its subprocess fallback because JPype was absent. Dependencies were installed
in an isolated temporary venv, not added to our core requirements. The upstream
requirements.txt contains unresolved merge markers; it was not installed.

## Observed results

| Entry point / engine | Returned tables | Observed behavior |
| --- | ---: | --- |
| PDFParser | 0 | Its pypdf-text whitespace heuristic finds no table. |
| PDFTableExtractor / pdfplumber | 0 | Promotes the first body row to column names, then crashes cleaning duplicate blank column names; exception becomes warning plus empty list. |
| PDFTableExtractor / Tabula | 1, 42 x 3 | First body row becomes column names (`資産の部`, `Unnamed: 0`, `Unnamed: 1`); year headers and unit absent. |
| PDFTableExtractor / Camelot stream | 1, 45 x 3 | Two year header rows followed by all 43 body rows; unit absent. |
| PDFTableExtractor / auto | 2 | Returns both Tabula and Camelot candidates; selects neither. |

Camelot's cleaned body, after explicitly removing its two header rows for this
comparison only, matches all 129 reference cells exactly. Tabula's remaining
42 body rows match 120/126 cells: four fullwidth parenthesis pairs become ASCII
and two fullwidth dashes become ASCII hyphens. These transformations originate
in that engine path; do not conflate them with upstream cleanup alone.

The pdfplumber path executes `pd.DataFrame(table[1:], columns=table[0])`.
On our sample this yields `['資産の部', '', '']`. Duplicate names make `df[col]`
a DataFrame rather than a Series; the cleaner's fallback raises “The truth value
of a Series is ambiguous.” The first body row is therefore not merely lost:
the entire table is discarded. These outcomes are dependency-version-specific;
actual versions are saved in results.json.

## Worth adopting

- Complementary engines and explicit per-engine runs. Camelot stream actually
  captures the year headers our ruled-table strategy misses on this sample.
- Configurable page selection and engine options; validate page bounds and use
  the same page contract for every engine.
- Separate table summaries and exports. Keep our canonical cells as source and
  construct DataFrames only as optional presentation views.
- Continue after a page/engine error, while retaining typed per-page errors and
  engine provenance as our pipeline already does.

## Implement differently

- Do not promote row zero automatically. Retain every row; infer header roles
  in a separate annotation layer using geometry. PDFParser's own Table class
  does retain row zero and uses synthetic Column_1 names: the promotion problem
  belongs to PDFTableExtractor's pdfplumber/Tabula paths, not both classes.
- PDFParser only uses pypdf; it is not the multiple-engine implementation. Its
  tabs/multiple-space splitting drops empty fields and geometry. It rejects
  uneven rows; section labels with blank amounts can break table continuity.
  Use geometry-based candidates and preserve blanks instead.
- `auto` is concatenate-and-deduplicate, despite its “best results” comment.
  Keep alternatives with engine-specific IDs; compare page/region overlap and
  reference quality explicitly. Never delete content-equal occurrences across
  pages or positions. An actual call to upstream `_remove_duplicate_tables`
  reduces two synthetic identical occurrences to one; the sample itself has no
  repeated physical tables, so that loss is a probe, not an observed sample loss.
- Avoid unconditional string conversion, strip, dropping empty rows/columns,
  and replacing literal 'nan'/'None'/'NaN' with blanks. Store derived text apart
  from engine raw strings. Avoid globally suppressing warnings.
- Never reduce exceptions to empty lists: distinguish failure, unavailable
  dependency, successful no-tables, and skipped OCR review.
- Preserve cell geometry, spans, page/table/cell IDs, and engine version/options;
  upstream DataFrames/Table objects do not retain these.
- Several PDFParser config fields (merge_cells, preserve_formatting, encoding,
  table_detection_threshold) are declared but unused in its extraction logic.
  Only expose settings whose behavior is implemented and tested.

## Implemented here

Added optional `camelot-stream` through our existing adapter contract, independently
implemented without copying upstream code. Default pdfplumber behavior is unchanged.
Camelot cell text (including trailing whitespace/newlines) remains verbatim;
normalization is a separate derived view. Geometry converts bottom-left engine
coordinates to top-left PDF points. Table bounds enclose emitted cells; Camelot's
original detection-region bounds are separately retained, already converted to
top-left coordinates. Engine-specific IDs distinguish its candidates.

This initial adapter handles stream grid cells with span 1. It rejects rotated
pages and nonzero media origins explicitly, rather than guessing coordinate
transforms. Header strings remain extracted rows, not semantic column assignments;
the unit is still page context. The optional integration test verifies 135 cell
IDs, first/header rows, a known coordinate, and body equivalence only after explicit
whitespace stripping. It does not claim 129 raw-string matches for this adapter.

```sh
pip install -r requirements.txt
python parse_pdf.py samples/financial-sample.pdf --engine camelot-stream --out output/camelot-stream
python -m unittest discover
```

To reproduce the upstream experiment with camelot-py 1.0.9, tabula-py 2.10.0,
pandas, pypdf, pdfplumber and Java installed:

```sh
python experiments/review_pdf_parse.py /path/to/pdf-parse-checkout
```

No upstream GPL-3.0 implementation was copied into the application.
