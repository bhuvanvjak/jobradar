"""Local review queue for job-board applications (the ones this project
will NOT auto-submit, to stay within LinkedIn/Naukri/ATS terms of
service). Run it, open http://localhost:5055, review each tailored
resume/cover letter, click "Open posting" to apply yourself on the real
site, then click "Mark Applied" so it gets logged as done. Nothing here
submits anything on your behalf - you always click the final Apply button.

Usage:
    python -m jobradar.apply.review_server
"""
from __future__ import annotations

from pathlib import Path

from flask import Flask, redirect, render_template_string, url_for

from ..store import Store
from . import applydb, notion_tracker

ROOT = Path(__file__).resolve().parent.parent.parent
app = Flask(__name__)

PAGE = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Job Application Review Queue</title>
<style>
  body { font-family: -apple-system, Segoe UI, Arial, sans-serif; max-width: 900px;
         margin: 30px auto; padding: 0 16px; background: #fafafa; color: #222; }
  h1 { font-size: 22px; }
  .empty { color: #666; padding: 40px 0; text-align: center; }
  .card { background: #fff; border: 1px solid #ddd; border-radius: 8px;
          padding: 18px 20px; margin-bottom: 18px; }
  .card h2 { margin: 0 0 4px 0; font-size: 17px; }
  .meta { color: #666; font-size: 13px; margin-bottom: 10px; }
  details { margin: 8px 0; }
  summary { cursor: pointer; font-weight: 600; font-size: 13px; color: #333; }
  pre { white-space: pre-wrap; font-family: inherit; font-size: 13px;
        background: #f4f4f4; padding: 10px; border-radius: 6px; }
  .actions { margin-top: 12px; display: flex; gap: 10px; }
  a.btn, button.btn { text-decoration: none; padding: 8px 14px; border-radius: 6px;
        font-size: 13px; border: none; cursor: pointer; }
  .btn-primary { background: #2563eb; color: #fff; }
  .btn-success { background: #16a34a; color: #fff; }
  .btn-muted { background: #e5e7eb; color: #333; }
</style>
</head>
<body>
  <h1>Pending Review ({{ items|length }})</h1>
  {% if not items %}
    <div class="empty">Nothing waiting on you right now.</div>
  {% endif %}
  {% for item in items %}
  <div class="card">
    <h2>{{ item.title }} — {{ item.company }}</h2>
    <div class="meta">{{ item.location }} · source: {{ item.source }} · score: {{ item.score }}/10</div>
    <details>
      <summary>Why this fits</summary>
      <pre>{{ item.why_fits }}</pre>
    </details>
    <details>
      <summary>Tailored resume</summary>
      <pre>{{ item.resume_md }}</pre>
    </details>
    <details>
      <summary>Cover letter</summary>
      <pre>{{ item.letter_text }}</pre>
    </details>
    <div class="actions">
      <a class="btn btn-primary" href="{{ item.url }}" target="_blank" rel="noopener">Open posting &amp; apply</a>
      <form method="post" action="{{ url_for('mark_applied', job_id=item.job_id) }}">
        <button class="btn btn-success" type="submit">Mark Applied</button>
      </form>
      <form method="post" action="{{ url_for('skip', job_id=item.job_id) }}">
        <button class="btn btn-muted" type="submit">Skip</button>
      </form>
    </div>
  </div>
  {% endfor %}
</body>
</html>
"""


def _store() -> Store:
    return Store(ROOT / "jobradar.db")


@app.route("/")
def index():
    store = _store()
    items = applydb.pending_review(store.db)
    return render_template_string(PAGE, items=items)


@app.route("/mark_applied/<job_id>", methods=["POST"])
def mark_applied(job_id):
    store = _store()
    row = store.db.execute(
        "SELECT notion_page_id FROM applications WHERE job_id = ?", (job_id,)
    ).fetchone()
    if row and row["notion_page_id"]:
        notion_tracker.update_status(row["notion_page_id"], "Applied - Job Board")
    applydb.set_status(store.db, job_id, "applied")
    return redirect(url_for("index"))


@app.route("/skip/<job_id>", methods=["POST"])
def skip(job_id):
    store = _store()
    row = store.db.execute(
        "SELECT notion_page_id FROM applications WHERE job_id = ?", (job_id,)
    ).fetchone()
    if row and row["notion_page_id"]:
        notion_tracker.update_status(row["notion_page_id"], "Skipped")
    applydb.set_status(store.db, job_id, "skipped")
    return redirect(url_for("index"))


def main():
    # 0.0.0.0 so it's reachable over Tailscale's virtual interface (and the
    # LAN), not just loopback. Safe here specifically because access is
    # gated by Tailscale's own device auth - only devices signed into your
    # tailnet can route to this machine at all; nothing changes for anyone
    # else. Still localhost-only from a browser on this PC either way.
    print("Review queue running at http://localhost:5055")
    print("Also reachable from your other Tailscale devices at http://<this-PC's-tailscale-ip>:5055")
    app.run(host="0.0.0.0", port=5055, debug=False)


if __name__ == "__main__":
    main()
