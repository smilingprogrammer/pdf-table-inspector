# PDF Table Inspector

Upload a financial PDF, compare detected tables with the source page, and download CSV, JSON or ZIP results.

## Deploy to Streamlit Community Cloud

Import this repository at https://share.streamlit.io and choose:

- Branch: `main`
- Main file: `deploy/app.py`
- Python: `3.12` in Advanced settings

No API keys or secrets are required. Click **Try sample PDF** after deployment.
See [DEPLOYMENT.md](DEPLOYMENT.md) for hosting details.

## Run locally

```sh
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run deploy/app.py
```

## Parser CLI

The parser does not import Streamlit. The single `requirements.txt` installs
the UI and all extraction engines for local use and hosting.

```sh
python parse_pdf.py samples/financial-sample.pdf --out output/tables
python parse_pdf.py samples/financial-sample.pdf --compare --pages 1 --out output/compare
```

Extraction preserves original strings, cell IDs, spans and top-left PDF-point
coordinates. Separate stages attach nearby headings, parse Decimal values using
explicit number formats, validate grids and report accounting differences.
Comparison retains candidates from ruled/text pdfplumber and stream/lattice
Camelot. Candidate scores are inspection aids, not correctness probabilities.
Image-only pages require OCR, which is not included.

## Reference and checks

The bundled public Japanese sample has 43 body rows and three columns. Its
reference transcription retains blanks, headings, unit and displayed accounting
differences under `data/`. Currency and scale remain separate from number formats.

The small regression suite covers the sample, numeric formats, UI rerun failures,
upload switching and the packaged app. Run with the deployment dependencies:

```sh
python run_tests.py
```

Optional engines that cannot run are reported separately from passing checks.
Generated outputs, secrets, local chat exports and uploaded files are excluded
from version control. The UI is read-only and uploads are limited to 25 MB.
