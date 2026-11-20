"""Copy the dataset CSV files from data/ into seed/ (the folder that goes into the repository and the Docker image).
The company in the data is fictional, so it is safe to commit.   python -m scripts.make_seed"""
import shutil
from pathlib import Path

src, dst = Path("data"), Path("seed")
if not src.exists():
    raise SystemExit("There is no data/ folder here. Run this from the project folder.")
dst.mkdir(exist_ok=True)
n = 0
for f in sorted(src.glob("*.csv")):
    shutil.copy(f, dst / f.name)
    n += 1
size = sum(f.stat().st_size for f in dst.glob("*.csv")) / 1e6
print(f"Copied {n} files ({size:.1f} MB) into seed/.  Now: git add seed")
