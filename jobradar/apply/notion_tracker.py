"""Logs every application (sent or pending review) to a Notion database so
you have one place to see everything the bot has done.

Expected database columns (create these exactly, matching types, before
first run - see README):
  Company        - Title
  Role           - Text
  Location       - Text
  Status         - Select  (Pending Review / Applied - Cold Email /
                             Applied - Job Board / Skipped / Replied /
                             Rejected / Interview)
  Channel        - Select  (Cold Email / Job Board)
  Source         - Select  (greenhouse / lever / ashby / workday / oracle /
                             atlassian / remotive / arbeitnow)
  Date Applied   - Date
  Job URL        - URL
  Why It Fits    - Text
  Resume File    - Text
  Letter/Email   - Text
"""
from __future__ import annotations

import os
from datetime import date

NOTION_TEXT_LIMIT = 1900  # stay under Notion's 2000-char rich_text limit


def _client():
    from notion_client import Client
    token = os.environ.get("NOTION_TOKEN", "")
    if not token:
        raise RuntimeError("NOTION_TOKEN not set (apply.notion.enabled is true)")
    return Client(auth=token)


def _trim(text: str) -> str:
    text = text or ""
    if len(text) <= NOTION_TEXT_LIMIT:
        return text
    return text[:NOTION_TEXT_LIMIT] + " …(truncated, full text in jobradar.db)"


def log_application(job, status: str, channel: str, why_fits: str,
                     resume_file: str, letter_text: str) -> str:
    """Creates a Notion page for this application. Returns the page id."""
    database_id = os.environ.get("NOTION_DATABASE_ID", "")
    if not database_id:
        raise RuntimeError("NOTION_DATABASE_ID not set (apply.notion.enabled is true)")

    notion = _client()
    props = {
        "Company": {"title": [{"text": {"content": job["company"] or "Unknown"}}]},
        "Role": {"rich_text": [{"text": {"content": job["title"] or ""}}]},
        "Location": {"rich_text": [{"text": {"content": job["location"] or ""}}]},
        "Status": {"select": {"name": status}},
        "Channel": {"select": {"name": channel}},
        "Source": {"select": {"name": job["source"] or "unknown"}},
        "Date Applied": {"date": {"start": date.today().isoformat()}},
        "Why It Fits": {"rich_text": [{"text": {"content": _trim(why_fits)}}]},
        "Resume File": {"rich_text": [{"text": {"content": resume_file or ""}}]},
        "Letter/Email": {"rich_text": [{"text": {"content": _trim(letter_text)}}]},
    }
    if job["url"]:
        props["Job URL"] = {"url": job["url"]}

    page = notion.pages.create(parent={"database_id": database_id}, properties=props)
    return page["id"]


def update_status(page_id: str, status: str) -> None:
    notion = _client()
    notion.pages.update(page_id=page_id, properties={"Status": {"select": {"name": status}}})
