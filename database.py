"""
database.py - SQLite persistence layer for EvalPro AI.

Uses SQLite for simplicity/portability of this mini-project demo.
To use MySQL instead (as listed in the project's software requirements),
swap the connection logic below for PyMySQL / mysql-connector-python,
keeping the same function signatures.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "evalpro.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT NOT NULL,
            image_path TEXT NOT NULL,
            model_answer TEXT NOT NULL,
            extracted_text TEXT,
            similarity_score REAL,
            marks_awarded REAL,
            max_marks REAL,
            feedback TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def save_result(student_name, image_path, model_answer, extracted_text,
                 similarity_score, marks_awarded, max_marks, feedback):
    conn = get_connection()
    cur = conn.execute("""
        INSERT INTO results
            (student_name, image_path, model_answer, extracted_text,
             similarity_score, marks_awarded, max_marks, feedback)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (student_name, image_path, model_answer, extracted_text,
          similarity_score, marks_awarded, max_marks, feedback))
    conn.commit()
    result_id = cur.lastrowid
    conn.close()
    return result_id


def get_all_results():
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM results ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return rows


def get_result_by_id(result_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM results WHERE id = ?", (result_id,)
    ).fetchone()
    conn.close()
    return row


def get_stats():
    """Summary numbers shown on the dashboard."""
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) AS n FROM results").fetchone()["n"]
    avg_row = conn.execute(
        "SELECT AVG(similarity_score) AS avg FROM results"
    ).fetchone()
    this_week = conn.execute(
        "SELECT COUNT(*) AS n FROM results "
        "WHERE created_at >= datetime('now', '-7 days')"
    ).fetchone()["n"]
    conn.close()
    avg_score = round(avg_row["avg"], 1) if avg_row["avg"] is not None else 0
    return {
        "total": total,
        "avg_score": avg_score,
        "this_week": this_week,
    }


def delete_results(ids):
    """Delete the given result ids. Returns the list of image filenames that
    belonged to the deleted rows so the caller can remove the files too."""
    ids = [int(i) for i in ids]
    if not ids:
        return []
    marks = ",".join("?" * len(ids))
    conn = get_connection()
    rows = conn.execute(
        f"SELECT image_path FROM results WHERE id IN ({marks})", ids
    ).fetchall()
    conn.execute(f"DELETE FROM results WHERE id IN ({marks})", ids)
    conn.commit()
    conn.close()
    return [r["image_path"] for r in rows]


def delete_all_results():
    conn = get_connection()
    rows = conn.execute("SELECT image_path FROM results").fetchall()
    conn.execute("DELETE FROM results")
    conn.commit()
    conn.close()
    return [r["image_path"] for r in rows]


def image_in_use(image_path):
    conn = get_connection()
    n = conn.execute(
        "SELECT COUNT(*) AS n FROM results WHERE image_path = ?", (image_path,)
    ).fetchone()["n"]
    conn.close()
    return n > 0
