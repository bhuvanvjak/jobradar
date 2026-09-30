"""Resume tailoring, cover letters, and cold emails for jobs jobradar has
already found and scored.

Notably does NOT make a separate "why does this fit" LLM call: jobradar's
scan already paid for that judgement (score + reason + breakdown in the
`jobs` table), so `why_it_fits` below just reformats it. One fewer model
call per job than a from-scratch tailoring pipeline would need.
"""
from __future__ import annotations

import json
import re

from . import llmclient

TAILOR_SYSTEM_PROMPT = """You are a careful resume editor helping a job \
candidate apply for jobs. You NEVER invent employers, job titles, dates, \
skills, or metrics that are not present in the candidate's base resume. \
Your job is to re-order, re-emphasize, and re-word existing content so it \
speaks directly to the target job description. If the base resume \
genuinely has nothing relevant to a requirement, do not fabricate \
something - just don't force a match for that requirement. Output exactly \
what is asked for and nothing else - no preamble like "Here is the..." \
and no closing remarks after the requested content."""


def _is_placeholder(value: str) -> bool:
    v = (value or "").strip()
    if not v:
        return True
    low = v.lower()
    return low.startswith("your ") or low == "you@example.com" or "xxx" in low


def _contact_block(candidate: dict) -> str:
    """Formats whatever real (non-placeholder) fields config.yaml's
    apply.candidate has into an explicit, authoritative contact block for
    the signature. Config.yaml is the source of truth when filled in -
    without this, the model is left guessing contact details from
    whatever it can infer out of the resume text, which works for a name
    sitting at the top of a resume but not reliably for a LinkedIn/GitHub
    handle that may not even appear there."""
    labels = [("name", "Name"), ("email", "Email"), ("phone", "Phone"),
              ("linkedin", "LinkedIn"), ("github", "GitHub")]
    lines = [f"{label}: {candidate[key]}" for key, label in labels
              if not _is_placeholder(candidate.get(key, ""))]
    if not lines:
        return ""
    return ("\nCandidate contact details (use exactly as given for the "
            "signature/contact line - do not invent or alter them):\n"
            + "\n".join(lines) + "\n")


def tailor_resume(cfg: dict, base_resume: str, job) -> str:
    prompt = f"""Base resume:
---
{base_resume}
---

Target job:
Title: {job['title']}
Company: {job['company']}
Location: {job['location'] or 'unspecified'}
Description:
{(job['description'] or '')[:4000]}
---

Rewrite the resume above so it is tailored to this specific job. Keep the \
same overall structure, sections, and length. Reorder bullet points so \
the most relevant ones come first, tighten wording toward this job's \
language, and adjust any summary/objective to speak directly to this \
role. Do not add any skill, employer, project, or number that isn't \
already in the base resume. Output ONLY the tailored resume, nothing \
else."""
    text = llmclient.complete(cfg, TAILOR_SYSTEM_PROMPT, prompt, max_tokens=2000)
    return _strip_code_fence(text)


def write_cover_letter(cfg: dict, base_resume: str, job, candidate: dict) -> str:
    prompt = f"""Candidate resume:
---
{base_resume}
---

Target job:
Title: {job['title']}
Company: {job['company']}
Location: {job['location'] or 'unspecified'}
Description:
{(job['description'] or '')[:3000]}
---
{_contact_block(candidate)}
Write a concise cover letter (under 300 words) applying for this role. \
Reference 1-2 concrete things from the resume that map to this job's \
actual requirements. No generic filler ("I am a hard worker"). No \
invented facts. Professional but human tone, not robotic. Sign off with \
the candidate's name - use the contact details above if given, otherwise \
take the name from the resume itself. Output ONLY the letter text."""
    text = llmclient.complete(cfg, TAILOR_SYSTEM_PROMPT, prompt, max_tokens=800)
    return _strip_code_fence(text)


def write_cold_email(cfg: dict, base_resume: str, job, candidate: dict) -> dict:
    prompt = f"""Candidate resume:
---
{base_resume}
---

Target company: {job['company']}
Role of interest: {job['title']}
Job context (may be partial):
{(job['description'] or '')[:2000]}
---
{_contact_block(candidate)}
Write a short, respectful cold email (under 150 words) to a recruiter/ \
hiring contact at this company, expressing interest in the \
"{job['title']}" role or similar openings. Reference 1 concrete, \
relevant thing from the resume. No generic flattery. Clear ask at the \
end (a short call, or to review the attached resume). Sign off with the \
candidate's name and, if given above, their LinkedIn/GitHub. Return \
ONLY valid JSON with keys "subject" and "body" (body is plain text, no \
markdown). No text before or after the JSON object."""
    text = llmclient.complete(cfg, TAILOR_SYSTEM_PROMPT, prompt, max_tokens=500)
    return _parse_email_json(text, job)


def why_it_fits(job) -> str:
    """No LLM call - reformats the score/reason/breakdown jobradar's own
    scan already computed for this job."""
    reason = (job["reason"] or "").strip()
    try:
        bd = json.loads(job["breakdown"]) if job["breakdown"] else {}
    except (TypeError, ValueError):
        bd = {}
    parts = [f"Score {job['score']}/10"]
    if reason:
        parts.append(reason)
    if bd:
        top = sorted(bd.items(), key=lambda kv: -kv[1])[:3]
        parts.append("strongest: " + ", ".join(f"{k} {v}" for k, v in top))
    return " - ".join(parts)


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return text.strip()


def _parse_email_json(text: str, job) -> dict:
    """Open models are less reliable than Claude at strict 'JSON only'
    instructions and sometimes wrap it in prose or a code fence - pull out
    the first {...} block rather than failing on the whole response."""
    cleaned = _strip_code_fence(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return {"subject": f"Interest in {job['title']} at {job['company']}", "body": cleaned}
