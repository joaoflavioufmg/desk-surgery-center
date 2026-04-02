from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
DOCS = ROOT / "docs"
INDEX = DOCS / "index.md"
FIGS = ROOT / "figs"
DOCS_FIGS = DOCS / "figs"

DOCS.mkdir(exist_ok=True)

# Read README
text = README.read_text(encoding="utf-8")

# Fix paths for MkDocs
text = text.replace("docs/figs/", "figs/")
text = text.replace("/docs/figs/", "figs/")

# Write index.md
INDEX.write_text(text, encoding="utf-8")

# Copy figures
if FIGS.exists():
    shutil.copytree(FIGS, DOCS_FIGS, dirs_exist_ok=True)

print("README synced to docs/index.md and figs copied.")
