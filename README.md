# EvalPro AI – Smart Answer Sheet Analyzer

Mini Project (BCC351) — Group No. 32
IMS Engineering College | AKTU (2025-26)

An AI/NLP/OCR-based system that automatically evaluates scanned answer sheets
against a model answer, assigns marks, and generates feedback:

```
Teacher Login → Upload Answer Sheet → OCR Text Extraction →
AI & NLP Evaluation → Automatic Marking → Store in Database →
Display Result & Feedback
```

This version is a full makeover of the original mini-project: the same
architecture and tech stack, with the OCR/text-cleaning bug fixed, a
redesigned interface ("Ledger & Ink" — a grade-register look built for both
a college demo and a professional walkthrough), and a few small AI-quality
improvements (key-term matching, OCR-failure detection).

## Tech Stack

- **Frontend:** HTML, CSS, JavaScript (via Flask/Jinja2 templates) — no
  build step, no framework, loads instantly.
- **Backend:** Python (Flask)
- **Database:** SQLite for this demo (swap for MySQL easily — see `database.py`)
- **AI Model:** Sentence-BERT (`all-MiniLM-L6-v2`) for semantic similarity,
  with an automatic TF-IDF fallback if the model can't be downloaded
- **OCR Tool:** Tesseract OCR (via `pytesseract`)

## 1. Prerequisites

Install Tesseract OCR on your machine (a separate program, not a Python
package):

- **Windows:** download the installer from
  https://github.com/UB-Mannheim/tesseract/wiki and install it
  (default path: `C:\Program Files\Tesseract-OCR\tesseract.exe` — the app
  now detects this automatically on Windows only, so macOS/Linux installs
  are left alone).
- **macOS:** `brew install tesseract`
- **Linux (Debian/Ubuntu):** `sudo apt install tesseract-ocr`

## 2. Setup

```bash
# 1. Create and activate a virtual environment (recommended)
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS/Linux

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Run the app
python app.py
```

The first run will try to download the Sentence-BERT model
(`all-MiniLM-L6-v2`, ~80 MB) — this needs an internet connection once. If it
can't download for any reason, the app automatically falls back to a TF-IDF
cosine-similarity comparison so it keeps working offline.

Open your browser at **http://127.0.0.1:5000**

## 3. Demo Login

```
Username: teacher
Password: admin123
```

Change this before any real deployment — either edit the fallback in
`app.py`, or set an environment variable instead of touching the code:

```bash
export EVALPRO_DEMO_PASSWORD="something-else"
export EVALPRO_SECRET_KEY="a-long-random-string"
```

## 4. How to Use

1. Log in as the teacher.
2. Click **"New evaluation"**.
3. Enter the student's name, upload a photo/scan of their handwritten or
   typed answer, paste the model/reference answer, and set the max marks.
4. EvalPro AI will:
   - Run OCR to extract the text from the image (or from each page of a PDF; digital PDFs use their embedded text)
   - Compute semantic similarity between the extracted answer and the
     model answer using Sentence-BERT (or TF-IDF offline)
   - Convert similarity → marks (proportional to max marks)
   - Surface the key terms shared between both answers
   - Generate a short feedback comment, and flag it clearly if OCR
     couldn't read the image (rather than silently mis-grading it)
   - Save everything to the database
5. View the result immediately, or browse all past evaluations — with
   summary stats — on the Dashboard.

## 5. What changed in this makeover

**Fixed:**
- `evaluator.py` was missing `import re`, which crashed every single
  upload (`NameError` inside `clean_text`).
- The Tesseract path was hardcoded to a Windows-only location and applied
  unconditionally, silently breaking OCR on macOS/Linux. It's now guarded
  to Windows only.
- Hardcoded plaintext password comparison replaced with a hashed check
  (`werkzeug.security`), and the secret key / demo password can now be
  overridden via environment variables instead of editing source.
- Added an 8 MB upload size limit and a friendly error page for oversized
  files.
- OCR failures are now detected and surfaced to the teacher (a flash
  warning + an inline notice on the result page) instead of silently
  grading garbled text as a real answer.

**Added:**
- A from-scratch visual redesign across all four pages (login, dashboard,
  upload, result) with a shared `base.html` layout, a real design system
  in `static/style.css`, and small interaction touches in `static/app.js`
  (drag-and-drop upload, an evaluating… loading state, auto-dismissing
  flash messages).
- Dashboard summary stats: total evaluations, average similarity score,
  and evaluations in the last 7 days (`database.get_stats()`).
- Key-term matching: a lightweight keyword-overlap check
  (`evaluator.extract_key_terms()`) shown as chips on the result page, so
  a teacher can see *what* the student actually covered — a simpler,
  dependency-free stand-in for the spaCy idea below.

## 6. Switching to MySQL (optional)

Your presentation lists MySQL as the database. To switch from the SQLite
demo setup to MySQL:

1. `pip install mysql-connector-python`
2. In `database.py`, replace the `sqlite3` connection with:
   ```python
   import mysql.connector
   def get_connection():
       return mysql.connector.connect(
           host="localhost", user="root", password="yourpassword",
           database="evalpro_ai"
       )
   ```
3. Update the `CREATE TABLE` syntax slightly (`AUTOINCREMENT` → `AUTO_INCREMENT`,
   `INTEGER PRIMARY KEY` → `INT AUTO_INCREMENT PRIMARY KEY`).
4. Use `%s` placeholders instead of `?` in the SQL queries.

## 7. Extending Further (ideas for Review 2/3, or a company pitch)

- Add full spaCy-based keyword/entity extraction in place of the simple
  overlap check, to highlight *which* key points a student missed.
- Support multi-question answer sheets (segment the OCR text per question).
- Add a student-facing login and personal result history.
- Add a "re-evaluate" / manual-override option for the teacher.
- Add a proper users table with per-teacher accounts instead of one shared
  hardcoded login.
- Add CSRF protection (Flask-WTF) on the forms before any public deployment.

## 8. Project Structure

```
evalpro-ai/
├── app.py                # Flask routes (login, upload, dashboard, result)
├── database.py            # SQLite persistence layer + dashboard stats
├── evaluator.py            # OCR + Sentence-BERT/NLP evaluation engine
├── requirements.txt
├── templates/
│   ├── base.html           # shared app shell (top bar, flash messages)
│   ├── login.html
│   ├── dashboard.html
│   ├── upload.html
│   └── result.html
├── static/
│   ├── style.css            # design system ("Ledger & Ink")
│   └── app.js               # dropzone, loading state, flash auto-dismiss
└── uploads/                 # uploaded answer-sheet images (created at runtime)
```
