"""Sends cold emails via SMTP, reusing jobradar's own email config
(config.yaml `email:` block + JOBRADAR_SMTP_PASSWORD env var - the exact
same account/credentials the weekly digest already uses, see
jobradar/digest.py). Only ever called with contacts YOU supplied
(data/target_companies.csv or an email explicitly found in a job's own
description) - this module does not discover or guess addresses.
"""
from __future__ import annotations

import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path


def send_cold_email(cfg: dict, to_email: str, subject: str, body: str,
                     attachment_path: Path | None = None) -> None:
    email_cfg = cfg["email"]
    password = (os.environ.get("JOBRADAR_SMTP_PASSWORD") or "").replace(" ", "").strip()
    if not password:
        raise RuntimeError("JOBRADAR_SMTP_PASSWORD is not set - export your Gmail App Password.")

    msg = MIMEMultipart()
    msg["From"] = email_cfg["from"]
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    if attachment_path and attachment_path.exists():
        with open(attachment_path, "rb") as f:
            part = MIMEApplication(f.read(), Name=attachment_path.name)
        part["Content-Disposition"] = f'attachment; filename="{attachment_path.name}"'
        msg.attach(part)

    with smtplib.SMTP(email_cfg["smtp_host"], email_cfg["smtp_port"], timeout=30) as server:
        server.starttls()
        server.login(email_cfg["from"], password)
        server.sendmail(email_cfg["from"], [to_email], msg.as_string())
