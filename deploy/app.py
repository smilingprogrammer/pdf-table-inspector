"""Community Cloud entry point; dependencies are in the root requirements.txt."""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from streamlit_app import main

main()
