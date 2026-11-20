import os
from pathlib import Path

collect_ignore = ["smoke_test.py"]

_root = Path(__file__).parent
for _d in ("data", "seed"):
    if (_root / _d / "departments.csv").exists():
        os.environ.setdefault("DATA_DIR", str(_root / _d))
        break
