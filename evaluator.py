"""
evaluator.py - The AI / NLP / OCR core of EvalPro AI.

Pipeline:
  1. extract_text_from_image()  -> Tesseract OCR
  2. evaluate_answer()          -> Sentence-BERT semantic similarity
                                    (falls back to TF-IDF cosine similarity
                                    if sentence-transformers isn't installed
                                    or the model can't be downloaded, so the
                                    app still runs on a light/offline machine)
  3. Automatic marking + feedback generation from the similarity score
  4. extract_key_terms()        -> lightweight keyword overlap, shown in the
                                    UI so a teacher can see *what* matched
"""

import os
import re
import platform

import pytesseract
from PIL import Image

# Tesseract's binary lives in different default places per OS. On Windows it
# is not on PATH by default, so point pytesseract at the standard install
# location. On macOS/Linux, `tesseract` is normally already on PATH (via
# `brew install tesseract` / `apt install tesseract-ocr`), so we leave it
# alone there rather than overwriting a working auto-detected path.
if platform.system() == "Windows":
    _default_win_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(_default_win_path):
        pytesseract.pytesseract.tesseract_cmd = _default_win_path


# A small stopword list is enough for surfacing "key terms" in a demo —
# no need for a full NLP stack just to filter out common words.
_STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "and", "or", "but", "if", "then", "so", "of", "in", "on", "at", "to",
    "for", "with", "as", "by", "from", "this", "that", "these", "those",
    "it", "its", "which", "who", "whom", "into", "about", "than", "also",
    "can", "will", "would", "should", "could", "has", "have", "had", "not",
    "there", "their", "they", "we", "you", "your", "our", "i", "he", "she",
}


# ---------------------------------------------------------------------
# OCR
# ---------------------------------------------------------------------
def extract_text_from_image(image_path):
    """Extract raw text from a scanned/photographed answer sheet."""
    try:
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img)
        cleaned = clean_text(text)
        if not cleaned:
            return "[OCR ERROR: no readable text was found in this image]"
        return cleaned
    except Exception as exc:
        # If Tesseract isn't installed/configured, fail gracefully
        # so the rest of the app is still demonstrable.
        return f"[OCR ERROR: {exc}]"


def extract_text_from_pdf(pdf_path, max_pages=30, dpi=200):
    """Extract text from a PDF answer sheet.

    Typed/digital PDFs: the embedded text is used directly (fast, exact).
    Scanned PDFs: each page is rendered to an image and run through OCR.
    PyMuPDF is used for both, so no extra system program (poppler) is needed.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return "[OCR ERROR: PDF support needs PyMuPDF — run: pip install pymupdf]"

    try:
        doc = fitz.open(pdf_path)
        pages = list(doc)[:max_pages]

        # 1) Digital PDF with real text -> no OCR needed
        embedded = clean_text(" ".join(p.get_text() for p in pages))
        if len(embedded) >= 40 * max(1, len(pages)) * 0.5:
            doc.close()
            return embedded

        # 2) Scanned PDF -> render each page and OCR it
        import io
        chunks = []
        zoom = dpi / 72
        for page in pages:
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            chunks.append(pytesseract.image_to_string(img))
        doc.close()
        cleaned = clean_text(" ".join(chunks))
        if not cleaned:
            return "[OCR ERROR: no readable text was found in this PDF]"
        return cleaned
    except Exception as exc:
        return f"[OCR ERROR: {exc}]"


def extract_text_from_file(path):
    """Route to the right extractor based on the file type."""
    if path.lower().endswith(".pdf"):
        return extract_text_from_pdf(path)
    return extract_text_from_image(path)


def ocr_failed(extracted_text):
    """True if extract_text_from_image() couldn't read the sheet."""
    return bool(extracted_text) and extracted_text.startswith("[OCR ERROR:")


def clean_text(text):
    text = text.replace("\n", " ").replace("\r", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ---------------------------------------------------------------------
# NLP semantic similarity (Sentence-BERT, with TF-IDF fallback)
# ---------------------------------------------------------------------
_sbert_model = None


def _get_sbert_model():
    """Lazy-load the Sentence-BERT model only once."""
    global _sbert_model
    if _sbert_model is None:
        from sentence_transformers import SentenceTransformer
        _sbert_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _sbert_model


def compute_similarity(student_answer, model_answer):
    """
    Returns a similarity score between 0 and 1.
    Tries Sentence-BERT first; falls back to TF-IDF cosine similarity
    if sentence-transformers / the model download isn't available.
    """
    if ocr_failed(student_answer) or not student_answer.strip():
        return 0.0

    try:
        from sentence_transformers import util
        model = _get_sbert_model()
        emb1 = model.encode(student_answer, convert_to_tensor=True)
        emb2 = model.encode(model_answer, convert_to_tensor=True)
        score = util.cos_sim(emb1, emb2).item()
        return max(0.0, min(1.0, score))
    except Exception:
        return _tfidf_similarity(student_answer, model_answer)


def _tfidf_similarity(student_answer, model_answer):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    if not student_answer.strip() or not model_answer.strip():
        return 0.0

    vectorizer = TfidfVectorizer()
    tfidf = vectorizer.fit_transform([student_answer, model_answer])
    score = cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0]
    return float(max(0.0, min(1.0, score)))


# ---------------------------------------------------------------------
# Key term overlap (lightweight — no spaCy dependency required)
# ---------------------------------------------------------------------
def extract_key_terms(student_answer, model_answer, limit=10):
    """
    Returns the significant words that appear in *both* answers, so a
    teacher can see at a glance which parts of the reference answer the
    student actually covered. This is intentionally simple (no spaCy/NER)
    so the app keeps working with only the base dependencies installed;
    see the README for how to extend this with proper entity extraction.
    """
    if ocr_failed(student_answer):
        return []

    def tokens(text):
        words = re.findall(r"[a-zA-Z][a-zA-Z\-]{2,}", text.lower())
        return {w for w in words if w not in _STOPWORDS}

    shared = tokens(student_answer) & tokens(model_answer)
    return sorted(shared)[:limit]


# ---------------------------------------------------------------------
# Automatic marking + feedback generation
# ---------------------------------------------------------------------
def generate_feedback(similarity, ocr_had_error=False):
    if ocr_had_error:
        return ("The uploaded image couldn't be read clearly, so no reliable "
                "score could be produced. Please re-upload a sharper photo "
                "or scan of the answer sheet.")
    if similarity >= 0.85:
        return ("Excellent! Your answer closely matches the expected "
                "response with strong conceptual accuracy.")
    elif similarity >= 0.65:
        return ("Good attempt. Most key points are covered, but some "
                "details could be more precise or complete.")
    elif similarity >= 0.40:
        return ("Partially correct. The answer touches on the topic but "
                "is missing several important points from the model answer.")
    else:
        return ("The answer does not align well with the expected response. "
                "Please revise the core concepts and try again.")


def evaluate_answer(student_answer, model_answer, max_marks):
    had_ocr_error = ocr_failed(student_answer)
    similarity = compute_similarity(student_answer, model_answer)
    marks = round(similarity * max_marks, 2)
    feedback = generate_feedback(similarity, ocr_had_error=had_ocr_error)
    key_terms = extract_key_terms(student_answer, model_answer)
    return {
        "similarity": round(similarity * 100, 2),  # as a percentage
        "marks": marks,
        "feedback": feedback,
        "key_terms": key_terms,
        "ocr_failed": had_ocr_error,
    }
