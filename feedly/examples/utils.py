from pathlib import Path

EXAMPLES_DIR = Path(__file__).parent
AUTH_DIR = EXAMPLES_DIR / "auth"
RESULTS_DIR = EXAMPLES_DIR / "results"

RESULTS_DIR.mkdir(exist_ok=True)
