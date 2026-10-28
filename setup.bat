import os, zipfile, shutil, re, textwrap, json
from pathlib import Path

src_zip = Path("/mnt/data/evalpro-ai(1).zip")
work = Path("/mnt/data/EvalPro_GitHub_Ready")
if work.exists():
    shutil.rmtree(work)
work.mkdir()

with zipfile.ZipFile(src_zip, "r") as z:
    z.extractall(work)

# Find actual project root (prefer folder containing app.py)
roots = [p for p in work.rglob("app.py") if p.is_file()]
if not roots:
    raise FileNotFoundError("app.py not found in ZIP")
app_path = roots[0]
root = app_path.parent

# Backup originals
backup = root / "_original_backup"
backup.mkdir(exist_ok=True)

# Patch evaluator.py: add re import if missing
for p in root.rglob("evaluator.py"):
    txt = p.read_text(encoding="utf-8", errors="ignore")
    if not re.search(r"^\s*import\s+re\b", txt, flags=re.M):
        txt = "import re\n" + txt
        p.write_text(txt, encoding="utf-8")

# Find files that reference Tesseract
tess_hits = []
for p in root.rglob("*.py"):
    txt = p.read_text(encoding="utf-8", errors="ignore")
    if "tesseract" in txt.lower():
        tess_hits.append(p)

# Patch hardcoded Tesseract paths conservatively
for p in tess_hits:
    txt = p.read_text(encoding="utf-8", errors="ignore")
    old = txt
    # Replace common hardcoded assignment with environment/config detection.
    pattern = r'pytesseract\.pytesseract\.tesseract_cmd\s*=\s*r?["\'][^"\']*tesseract\.exe["\']'
    if re.search(pattern, txt, flags=re.I):
        replacement = (
            'pytesseract.pytesseract.tesseract_cmd = os.environ.get("TESSERACT_CMD") or '
            'shutil.which("tesseract") or '
            'r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"'
        )
        if "import os" not in txt:
            txt = "import os\n" + txt
        if "import shutil" not in txt:
            txt = "import shutil\n" + txt
        txt = re.sub(pattern, replacement, txt, flags=re.I)
    if txt != old:
        p.write_text(txt, encoding="utf-8")

# Read existing requirements, or generate based on imports
req = root / "requirements.txt"
if not req.exists():
    imports = set()
    for p in root.rglob("*.py"):
        txt = p.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r"^\s*(?:import|from)\s+([A-Za-z_][A-Za-z0-9_]*)", txt, re.M):
            imports.add(m.group(1).lower())
    mapping = {
        "flask":"Flask", "flask_sqlalchemy":"Flask-SQLAlchemy",
        "sqlalchemy":"SQLAlchemy", "pytesseract":"pytesseract",
        "PIL":"Pillow", "cv2":"opencv-python", "numpy":"numpy",
        "werkzeug":"Werkzeug", "jinja2":"Jinja2", "requests":"requests",
    }
    packages = [mapping[k] for k in sorted(imports) if k in mapping]
    if "Flask" not in packages: packages.insert(0, "Flask")
    req.write_text("\n".join(packages) + "\n", encoding="utf-8")

# GitHub files
(root / ".gitignore").write_text(textwrap.dedent("""\
venv/
.venv/
__pycache__/
*.py[cod]
*.log
.env
.env.*
.vscode/
.idea/
.DS_Store
Thumbs.db
instance/
"""), encoding="utf-8")

(root / ".env.example").write_text(textwrap.dedent("""\
# Optional: set this only if Tesseract is installed somewhere non-standard.
# Example:
# TESSERACT_CMD=C:\\Program Files\\Tesseract-OCR\\tesseract.exe
"""), encoding="utf-8")

(root / "setup.bat").write_text(textwrap.dedent(r"""\
@echo off
setlocal
title EvalPro AI - Setup

echo ==========================================
echo        EvalPro AI - First Time Setup
echo ==========================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found.
    echo Install Python 3.10+ and enable "Add Python to PATH".
    pause
    exit /b 1
)

echo [1/4] Creating virtual environment...
if not exist "venv\Scripts\python.exe" (
    python -m venv venv
)

echo [2/4] Installing Python dependencies...
call "venv\Scripts\python.exe" -m pip install --upgrade pip
if exist "requirements.txt" (
    call "venv\Scripts\python.exe" -m pip install -r requirements.txt
) else (
    echo [WARNING] requirements.txt not found.
)

echo [3/4] Checking Tesseract OCR...
where tesseract >nul 2>nul
if not errorlevel 1 (
    echo Tesseract found in PATH.
) else if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (
    echo Tesseract found at default Windows location.
) else (
    echo [WARNING] Tesseract OCR was not found.
    echo Install Tesseract OCR, then run setup.bat again.
)

echo [4/4] Setup complete.
echo.
echo Run EvalPro using run.bat
pause
"""), encoding="utf-8")

(root / "run.bat").write_text(textwrap.dedent(r"""\
@echo off
setlocal
title EvalPro AI

if not exist "venv\Scripts\python.exe" (
    echo Virtual environment not found.
    echo Please run setup.bat first.
    pause
    exit /b 1
)

echo Starting EvalPro AI...
echo Open http://127.0.0.1:5000 in your browser.
echo Press Ctrl+C to stop the server.
echo.

call "venv\Scripts\python.exe" app.py
pause
"""), encoding="utf-8")

(root / "README_GITHUB.md").write_text(textwrap.dedent("""\
# EvalPro AI

Smart Answer Sheet Analyzer built with Flask, OCR/Tesseract and SQLite.

## Run on another Windows laptop

### 1. Install
- Python 3.10+ (recommended)
- Git
- Tesseract OCR

During Python installation, enable **Add Python to PATH**.

### 2. Clone
```powershell
git clone YOUR_GITHUB_REPOSITORY_URL
cd evalpro-ai