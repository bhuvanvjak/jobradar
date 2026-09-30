"""SQLite state for the auto-apply module.

Lives in a separate `applications` table in the same jobradar.db, keyed by
the `jobs` table's id, rather than new columns on `jobs` - so jobradar's own
schema and migrations stay untouched and this module could be removed
without the scanner ever noticing it was there.
"""
from __future__ import annotations

import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS applications (
    job_id          TEXT PRIMARY KEY,
    channel         TEXT NOT NULL,      -- 'cold_email' | 'job_board'
    status          TEXT NOT NULL,      -- 'pending_review' | 'applied' | 'skipped'
    resume_md       TEXT,
    resume_pdf      TEXT,
    letter_text     TEXT,
    why_fits        TEXT,
    contact_email   TEXT,
    notion_page_id  TEXT,
    created_at      REAL NOT NULL,
    applied_at      REAL
);
"""


def init(db: sqlite3.Connection) -> None:
    db.executescript(SCHEMA)
    db.commit()


def candidates(db: sqlite3.Connection, min_score: int, limit: int) -> list[sqlite3.Row]:
    """Scored, open jobs at/above min_score with no application row yet."""
    return db.execute(
        """SELECT j.* FROM jobs j
           LEFT JOIN applications a ON a.job_id = j.id
           WHERE j.closed_at IS NULL AND j.score IS NOT NULL AND j.score >= ?
             AND a.job_id IS NULL
           ORDER BY j.score DESC, j.first_seen DESC
           LIMIT ?""",
        (min_score, limit),
    ).fetchall()


def record(db: sqlite3.Connection, job_id: str, channel: str, status: str, *,
           resume_md: str = "", resume_pdf: str = "", letter_text: str = "",
           why_fits: str = "", contact_email: str = "", notion_page_id: str = "") -> None:
    now = time.time()
    db.execute(
        """INSERT INTO applications (job_id, channel, status, resume_md, resume_pdf,
                                     letter_text, why_fits, contact_email,
                                     notion_page_id, created_at, applied_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(job_id) DO UPDATE SET
             channel=excluded.channel, status=excluded.status,
             resume_md=excluded.resume_md, resume_pdf=excluded.resume_pdf,
             letter_text=excluded.letter_text, why_fits=excluded.why_fits,
             contact_email=excluded.contact_email, notion_page_id=excluded.notion_page_id""",
        (job_id, channel, status, resume_md, resume_pdf, letter_text, why_fits,
         contact_email, notion_page_id, now, now if status == "applied" else None),
    )
    db.commit()


def pending_review(db: sqlite3.Connection) -> list[sqlite3.Row]:
    return db.execute(
        """SELECT a.*, j.title, j.company, j.location, j.url, j.source
           FROM applications a JOIN jobs j ON j.id = a.job_id
           WHERE a.status = 'pending_review'
           ORDER BY a.created_at DESC"""
    ).fetchall()


def set_status(db: sqlite3.Connection, job_id: str, status: str) -> None:
    db.execute(
        "UPDATE applications SET status = ?, applied_at = ? WHERE job_id = ?",
        (status, time.time() if status == "applied" else None, job_id),
    )
    db.commit()


def stats(db: sqlite3.Connection) -> dict:
    row = db.execute(
        """SELECT COUNT(*) total,
                  SUM(status = 'applied') applied,
                  SUM(status = 'pending_review') pending
           FROM applications"""
    ).fetchone()
    return {"total": row["total"] or 0, "applied": row["applied"] or 0,
            "pending": row["pending"] or 0}
