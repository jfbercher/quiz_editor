# streamlit_app.py

import sys
from pathlib import Path

# Ajouter src au PYTHONPATH
sys.path.append(str(Path(__file__).parent / "src"))

from quiz_editor.quiz_editor import main

if __name__ == "__main__":
    main()