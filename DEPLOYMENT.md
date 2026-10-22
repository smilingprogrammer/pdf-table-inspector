# Host the PDF table inspector

## Streamlit Community Cloud

1. Create a GitHub repository and upload this project, including `.streamlit/`,
   `ui/`, `financial_parser/`, `samples/financial-sample.pdf`, and `deploy/`.
2. At https://share.streamlit.io choose **Create app**, then select your repository
   and branch.
3. Set **Main file path** to **deploy/app.py**.
4. In **Advanced settings**, select **Python 3.12**. No secrets are required.
5. Deploy, then click **Try sample PDF**. Confirm the 43-row ruled candidate and
   its year headings, and download a CSV.

The root `requirements.txt` is the only dependency file. It includes Streamlit,
pdfplumber and both Camelot routes. No Java, Ghostscript, OCR service or API key
is required. Rendering uses PDFium and headless OpenCV.

Official guides: [dependencies](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies)
and [deployment and Python selection](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy).

## Standalone ZIP

Run `python scripts/package_streamlit.py` to build
`dist/pdf-table-inspector-streamlit.zip`. Extract it and upload the contents of
its `pdf-table-inspector/` folder to a GitHub repository. For this standalone
package choose **streamlit_app.py** as the main file: its root requirements.txt
already contains all deployment dependencies. Select Python 3.12.

The archive contains only runtime code, the public sample, styling/configuration,
CLI helpers, reference data and this guide. Generated outputs, uploaded PDFs,
temporary files, environment folders, tests and secrets are excluded. A SHA-256
manifest accompanies the package and is also included inside it.

## Run the exact hosting dependencies locally

```sh
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run deploy/app.py
```

For the extracted standalone ZIP, install `requirements.txt` and run
`streamlit run streamlit_app.py` from its root folder instead.

## Operation

The first version is read-only. Uploads are limited to 25 MB. Each extraction has
an isolated worker and a 45-second timeout; request fewer pages for large files.
Worker outputs and source bytes stay in the user's session, with temporary worker
folders cleaned up after each run. Downloads can include the original uploaded
PDF. No shared parsing cache is used. A hosted app still consumes memory for
active sessions; comparison runs all four routes and uses more resources than
the Automatic default.

Scanned/image-only pages show an OCR-required message; OCR is not included.
Tables/candidate scores are inspection aids, not accounting correctness guarantees.
Access to a deployed app is controlled in your Streamlit hosting settings.

## Checks (full source checkout)

The package smoke test imports from the extracted archive, runs the real worker,
checks all 129 body cells and 7 header/unit cells against the reference, and
exercises the empty state and sample button using Streamlit AppTest. Tests stay
in the full source checkout rather than the runtime ZIP. From that checkout run:

```sh
python -m unittest test_deployment -v
```

Cloud-ready packaging is not a deployment: this project has not been pushed to
GitHub or published to Community Cloud by the packaging command.
