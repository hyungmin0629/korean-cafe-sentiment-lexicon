"""Start the local CSV upload and report application from a source checkout."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from cafe_sentiment.web import main

if __name__ == "__main__":
    raise SystemExit(main())
