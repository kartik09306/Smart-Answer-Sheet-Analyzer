import os
import secrets
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, send_from_directory, abort
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from database import (
    init_db, save_result, get_all_results, get_result_by_id, get_stats,
    delete_results, delete_all_results, image_in_use,
)
from evaluator import extract_text_from_file, evaluate_answer

# ---------------------------------------------------------------------
# App configuration
# ---------------------------------------------------------------------
app = Flask(__name__)

# Prefer a secret key from the environment in real deployments; fall back to
# a fixed dev value so the app still runs out of the box for the demo/college
# submission. Set valero_SECRET_KEY before deploying anywhere real.
app.secret_key = os.environ.get("EVALPRO_SECRET_KEY", "dev-only-change-me-before-deploying")

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20 MB upload limit (PDFs can be large)

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Hardcoded teacher credentials for demo purposes. The password is hashed
# (rather than compared as plain text) so the check mirrors how a real login
# would work; still swap this whole block for a users table + hashed
# passwords stored in the DB before any real deployment.
TEACHER_USERNAME = "teacher"
TEACHER_PASSWORD_HASH = generate_password_hash(
    os.environ.get("EVALPRO_DEMO_PASSWORD", "admin123")
)

MAX_MARKS_DEFAULT = 10


def allowed_file(filename):
    return "." in filename and \
        filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get("logged_in"):
            flash("Please log in first.", "error")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)
    return wrapped


# ---------------------------------------------------------------------
# CSRF protection + template helpers
# ---------------------------------------------------------------------
def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    return session["_csrf"]


app.jinja_env.globals["csrf_token"] = csrf_token


def require_csrf():
    sent = request.form.get("_csrf", "")
    if not sent or not secrets.compare_digest(sent, session.get("_csrf", "")):
        abort(400, "Invalid or missing security token. Please reload the page and try again.")


@app.template_filter("grade")
def grade_filter(marks, max_marks):
    """Letter grade from marks / max_marks."""
    try:
        pct = float(marks) / float(max_marks) * 100
    except (TypeError, ValueError, ZeroDivisionError):
        return "–"
    for cutoff, g in ((90, "O"), (80, "A+"), (70, "A"), (60, "B+"), (50, "B"), (40, "C")):
        if pct >= cutoff:
            return g
    return "F"


@app.template_filter("is_pdf")
def is_pdf_filter(filename):
    return str(filename).lower().endswith(".pdf")


@app.template_filter("pct")
def pct_filter(marks, max_marks):
    try:
        return round(float(marks) / float(max_marks) * 100)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0


def remove_uploaded_files(filenames):
    """Delete stored sheet images that no remaining record refers to."""
    root = os.path.abspath(app.config["UPLOAD_FOLDER"])
    for name in set(filenames):
        if not name or image_in_use(name):
            continue
        path = os.path.abspath(os.path.join(root, os.path.basename(name)))
        if path.startswith(root + os.sep) and os.path.isfile(path):
            try:
                os.remove(path)
            except OSError:
                pass


# ---------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------
@app.route("/")
def index():
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if username == TEACHER_USERNAME and check_password_hash(TEACHER_PASSWORD_HASH, password):
            session["logged_in"] = True
            session["username"] = username
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@app.route("/uploads/<path:filename>")
@login_required
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    results = get_all_results()
    stats = get_stats()
    return render_template("dashboard.html", results=results, stats=stats, active_nav="dashboard")


@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "POST":
        student_name = request.form.get("student_name", "").strip()
        model_answer = request.form.get("model_answer", "").strip()
        max_marks = request.form.get("max_marks", str(MAX_MARKS_DEFAULT)).strip()
        file = request.files.get("answer_sheet")

        if not student_name or not model_answer:
            flash("Student name and model answer are required.", "error")
            return redirect(url_for("upload"))

        if not file or file.filename == "":
            flash("Please select an answer sheet (image or PDF) to upload.", "error")
            return redirect(url_for("upload"))

        if not allowed_file(file.filename):
            flash("Only PNG, JPG, JPEG or PDF files are supported.", "error")
            return redirect(url_for("upload"))

        try:
            max_marks = float(max_marks)
            if max_marks <= 0:
                raise ValueError
        except ValueError:
            max_marks = MAX_MARKS_DEFAULT

        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        stored_name = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], stored_name)
        file.save(filepath)

        # --- OCR Text Extraction ---
        extracted_text = extract_text_from_file(filepath)

        # --- AI & NLP Evaluation + Automatic Marking + Feedback ---
        evaluation = evaluate_answer(extracted_text, model_answer, max_marks)

        if evaluation["ocr_failed"]:
            flash(
                "The sheet couldn't be read clearly, so this score may be unreliable. "
                "Consider re-uploading a sharper photo or scan.",
                "warning",
            )

        # --- Store in Database ---
        result_id = save_result(
            student_name=student_name,
            image_path=stored_name,
            model_answer=model_answer,
            extracted_text=extracted_text,
            similarity_score=evaluation["similarity"],
            marks_awarded=evaluation["marks"],
            max_marks=max_marks,
            feedback=evaluation["feedback"],
        )

        return redirect(url_for("result", result_id=result_id))

    return render_template("upload.html", default_max_marks=MAX_MARKS_DEFAULT, active_nav="upload")


@app.route("/result/<int:result_id>")
@login_required
def result(result_id):
    record = get_result_by_id(result_id)
    if record is None:
        flash("Result not found.", "error")
        return redirect(url_for("dashboard"))

    from evaluator import extract_key_terms, ocr_failed
    key_terms = extract_key_terms(record["extracted_text"], record["model_answer"])
    failed = ocr_failed(record["extracted_text"])

    return render_template(
        "result.html", r=record, key_terms=key_terms, ocr_failed=failed, active_nav=None
    )


@app.route("/result/<int:result_id>/delete", methods=["POST"])
@login_required
def delete_result(result_id):
    require_csrf()
    if get_result_by_id(result_id) is None:
        flash("Evaluation not found — it may already have been deleted.", "error")
    else:
        remove_uploaded_files(delete_results([result_id]))
        flash("Evaluation deleted.", "success")
    return redirect(url_for("dashboard"))


@app.route("/results/delete", methods=["POST"])
@login_required
def delete_selected():
    require_csrf()
    ids = [i for i in request.form.getlist("ids") if i.isdigit()]
    if not ids:
        flash("Select at least one evaluation to delete.", "warning")
        return redirect(url_for("dashboard"))
    remove_uploaded_files(delete_results(ids))
    flash(f"{len(ids)} evaluation{'s' if len(ids) != 1 else ''} deleted.", "success")
    return redirect(url_for("dashboard"))


@app.route("/results/delete-all", methods=["POST"])
@login_required
def delete_all():
    require_csrf()
    files = delete_all_results()
    remove_uploaded_files(files)
    flash("All evaluations deleted.", "success")
    return redirect(url_for("dashboard"))


@app.errorhandler(400)
def bad_request(exc):
    flash(getattr(exc, "description", "Bad request."), "error")
    return redirect(url_for("dashboard") if session.get("logged_in") else url_for("login"))


@app.errorhandler(413)
def file_too_large(_exc):
    flash("That file is too large — please upload a file under 20 MB.", "error")
    return redirect(url_for("upload"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
