"""Orchestrates one auto-apply batch: pull the best unapplied scored jobs
from jobradar's own store, tailor a resume + cover letter/cold email for
each with an LLM, route to cold email (sent) or the review queue (your
one-click approval), and log everything to Notion.

Note: job descriptions come from jobradar's `jobs` table, which trims them
to 1500 characters on ingest (see store.py) to keep the database small
across thousands of tracked postings. That is usually enough to tailor
against - most postings put the real requirements up front - but is a
known simplification, not the full original listing.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

from jobradar.resume import extract_text

from . import applydb, emailer, notion_tracker, pdf_export, tailor

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def _load_target_companies(path: Path) -> dict:
    """company name (lowercased) -> contact email, from a CSV you maintain
    yourself. Nothing here scrapes or guesses addresses."""
    contacts = {}
    if not path.exists():
        return contacts
    with open(path, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            company = (row.get("company") or "").strip().lower()
            email = (row.get("contact_email") or "").strip()
            if company and email:
                contacts[company] = email
    return contacts


def _safe_filename(text: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in (text or ""))[:60]


def run_batch(cfg: dict, store, root: Path, dry_run: bool = False) -> dict:
    apply_cfg = cfg.get("apply", {})
    if not apply_cfg.get("enabled", False):
        print("apply.enabled is false in config.yaml - nothing to do.")
        return {"applied": 0, "queued": 0}

    applydb.init(store.db)

    resume_path = Path(cfg["resume_path"])
    if not resume_path.is_absolute():
        resume_path = root / resume_path
    base_resume = extract_text(resume_path)
    candidate = apply_cfg.get("candidate", {})

    count = int(apply_cfg.get("jobs_per_batch", 5))
    min_score = int(apply_cfg.get("min_score", 6))
    jobs = applydb.candidates(store.db, min_score, count)
    if not jobs:
        print(f"Nothing new to apply to (no unapplied job scored >= {min_score}). "
              f"Run 'jobradar scan' first if you haven't recently.")
        return {"applied": 0, "queued": 0}

    out_dir = root / "apply_output"
    out_dir.mkdir(exist_ok=True)

    cold_cfg = apply_cfg.get("cold_email", {})
    contacts_path = root / cold_cfg.get("contacts_file", "data/target_companies.csv")
    contacts = _load_target_companies(contacts_path)
    cold_budget = int(cold_cfg.get("max_per_batch", 2)) if cold_cfg.get("enabled") else 0
    notion_on = apply_cfg.get("notion", {}).get("enabled", True)

    applied, queued = 0, 0
    for job in jobs:
        print(f"\ntailoring: {job['title']} @ {job['company']} (score {job['score']}/10)")
        resume_md = tailor.tailor_resume(cfg, base_resume, job)
        why_fits = tailor.why_it_fits(job)

        fname_base = f"{_safe_filename(job['company'])}_{_safe_filename(job['title'])}_{job['id'][:8]}"
        resume_pdf_path = out_dir / f"{fname_base}_resume.pdf"
        if not dry_run:
            pdf_export.markdown_to_pdf(resume_md, resume_pdf_path)
        (out_dir / f"{fname_base}_resume.txt").write_text(resume_md, encoding="utf-8")

        desc_match = EMAIL_RE.search(job["description"] or "")
        # An email already printed in the posting counts as the company
        # inviting contact - your own contacts file takes priority either way.
        contact_email = contacts.get(job["company"].strip().lower(), "") or \
            (desc_match.group(0) if desc_match else "")
        use_cold_email = bool(contact_email) and cold_budget > 0

        if use_cold_email:
            cold_budget -= 1
            email_draft = tailor.write_cold_email(cfg, base_resume, job, candidate)
            letter_text = f"Subject: {email_draft['subject']}\n\n{email_draft['body']}"
            (out_dir / f"{fname_base}_coldemail.txt").write_text(letter_text, encoding="utf-8")

            if dry_run:
                print(f"  [dry-run] would send cold email to {contact_email}")
                continue

            status, notion_status = "pending_review", "Pending Review"
            if cold_cfg.get("send_automatically", True):
                emailer.send_cold_email(cfg, contact_email, email_draft["subject"],
                                         email_draft["body"], resume_pdf_path)
                status, notion_status = "applied", "Applied - Cold Email"
                applied += 1
                print(f"  sent cold email to {contact_email}")
            else:
                queued += 1
                print("  cold email drafted but send_automatically=false; held for review")

            notion_page_id = notion_tracker.log_application(
                job, notion_status, "Cold Email", why_fits, str(resume_pdf_path), letter_text
            ) if notion_on else ""
            applydb.record(store.db, job["id"], "cold_email", status,
                           resume_md=resume_md, resume_pdf=str(resume_pdf_path),
                           letter_text=letter_text, why_fits=why_fits,
                           contact_email=contact_email, notion_page_id=notion_page_id)

        else:
            cover_letter = tailor.write_cover_letter(cfg, base_resume, job, candidate)
            (out_dir / f"{fname_base}_cover.txt").write_text(cover_letter, encoding="utf-8")

            if dry_run:
                print("  [dry-run] would queue for job-board review")
                continue

            notion_page_id = notion_tracker.log_application(
                job, "Pending Review", "Job Board", why_fits, str(resume_pdf_path), cover_letter
            ) if notion_on else ""
            applydb.record(store.db, job["id"], "job_board", "pending_review",
                           resume_md=resume_md, resume_pdf=str(resume_pdf_path),
                           letter_text=cover_letter, why_fits=why_fits,
                           notion_page_id=notion_page_id)
            queued += 1
            print("  queued for review (run: jobradar review)")

    print(f"\n{applied} applied, {queued} queued for review.")
    return {"applied": applied, "queued": queued}
