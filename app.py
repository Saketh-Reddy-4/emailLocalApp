from __future__ import annotations

import os
import random
import smtplib
import ssl
import time
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import pandas as pd
import streamlit as st

REQUIRED_COLUMNS = ["company", "hr_name", "email", "position"]
LOG_PATH = Path("logs/sent_log.csv")
CONFIG_PATH = Path("config.json")
TEMPLATE_PATH = Path("email_template.txt")


def ensure_files() -> None:
    Path("logs").mkdir(exist_ok=True)

    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(
            '{\n'
            '  "candidate_name": "Your Name",\n'
            '  "candidate_phone": "+1-000-000-0000",\n'
            '  "candidate_email": "you@example.com",\n'
            '  "default_subject": "Application for {position} - {candidate_name}"\n'
            '}\n',
            encoding="utf-8",
        )

    if not TEMPLATE_PATH.exists():
        TEMPLATE_PATH.write_text(
            "Dear {hr_name},\n\n"
            "I am writing to apply for the {position} role at {company}.\n"
            "Please find my resume attached.\n\n"
            "Regards,\n{candidate_name}\n{candidate_phone}\n{candidate_email}\n",
            encoding="utf-8",
        )

    if not LOG_PATH.exists():
        pd.DataFrame(
            columns=["date", "timestamp", "email", "company", "status", "reason"]
        ).to_csv(LOG_PATH, index=False)


def load_config() -> dict:
    return pd.read_json(CONFIG_PATH, typ="series").to_dict()


def load_template() -> str:
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def already_sent_today(email: str) -> bool:
    df = pd.read_csv(LOG_PATH)
    if df.empty:
        return False

    today = datetime.now().date().isoformat()
    sent_today = df[
        (df["date"] == today)
        & (df["email"].str.lower() == email.lower())
        & (df["status"] == "Sent")
    ]
    return not sent_today.empty


def log_row(email: str, company: str, status: str, reason: str = "") -> None:
    row = {
        "date": datetime.now().date().isoformat(),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "email": email,
        "company": company,
        "status": status,
        "reason": reason,
    }
    pd.DataFrame([row]).to_csv(LOG_PATH, mode="a", header=False, index=False)


def send_email(
    hr_name: str,
    email: str,
    company: str,
    position: str,
    subject: str,
    body: str,
    resume_path: str | None,
) -> tuple[bool, str]:
    del hr_name, company, position  # kept for signature compatibility and feature parity

    sender = os.getenv("EMAIL_AUTOMATION_SENDER", "").strip()
    app_password = os.getenv("EMAIL_AUTOMATION_APP_PASSWORD", "").strip()
    if not sender or not app_password:
        return False, "Missing EMAIL_AUTOMATION_SENDER or EMAIL_AUTOMATION_APP_PASSWORD"

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    if resume_path:
        path = Path(resume_path)
        if not path.exists():
            return False, f"Resume not found: {resume_path}"

        with path.open("rb") as file_obj:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(file_obj.read())

        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename={path.name}")
        msg.attach(part)

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls(context=ssl.create_default_context())
            server.login(sender, app_password)
            server.sendmail(sender, email, msg.as_string())
        return True, ""
    except Exception as exc:
        return False, str(exc)


def render_body(template: str, cfg: dict, hr_name: str, company: str, position: str) -> str:
    return template.format(
        hr_name=hr_name,
        company=company,
        position=position,
        candidate_name=cfg.get("candidate_name", ""),
        candidate_phone=cfg.get("candidate_phone", ""),
        candidate_email=cfg.get("candidate_email", ""),
    )


def save_uploaded_resume(uploaded_file) -> str:
    destination = Path("logs") / uploaded_file.name
    destination.write_bytes(uploaded_file.getbuffer())
    return str(destination)


def render_single_tab(config: dict, template: str) -> None:
    hr_name = st.text_input("Recipient name", value="Hiring Manager", key="single_name")
    recipient_email = st.text_input("Recipient email", key="single_email")
    company = st.text_input("Company", key="single_company")
    position = st.text_input("Position", key="single_position")

    default_subject = str(
        config.get("default_subject", "Application for {position} - {candidate_name}")
    ).format(position=position or "Role", candidate_name=config.get("candidate_name", ""))
    subject = st.text_input("Subject", value=default_subject)

    uploaded_resume = st.file_uploader(
        "Upload resume", type=["pdf", "doc", "docx"], key="single_resume"
    )
    resume_path_input = st.text_input(
        "Or provide local resume path", key="single_resume_path"
    )

    body = render_body(template, config, hr_name, company, position)
    st.text_area("Email preview", value=body, height=220)

    if st.button("Send Single Email"):
        if already_sent_today(recipient_email):
            st.warning("Duplicate skipped: recipient already sent today.")
            log_row(recipient_email, company, "Skipped", "Duplicate same day")
            return

        resume_path = None
        if uploaded_resume is not None:
            resume_path = save_uploaded_resume(uploaded_resume)
        elif resume_path_input.strip():
            resume_path = resume_path_input.strip()

        ok, reason = send_email(
            hr_name,
            recipient_email,
            company,
            position,
            subject,
            body,
            resume_path,
        )
        if ok:
            st.success("Email sent.")
            log_row(recipient_email, company, "Sent", "")
        else:
            st.error(reason)
            log_row(recipient_email, company, "Failed", reason)


def render_batch_tab(config: dict, template: str) -> None:
    csv_file = st.file_uploader("Upload CSV", type=["csv"], key="batch_csv")
    min_delay = st.number_input("Min delay (seconds)", min_value=0, value=180)
    max_delay = st.number_input("Max delay (seconds)", min_value=0, value=420)
    daily_max = st.number_input("Daily max sends", min_value=1, value=120)
    dry_run = st.checkbox("Dry run", value=True)

    uploaded_resume = st.file_uploader(
        "Upload resume", type=["pdf", "doc", "docx"], key="batch_resume"
    )
    resume_path_input = st.text_input(
        "Or provide local resume path", key="batch_resume_path"
    )

    if csv_file is None:
        return

    df = pd.read_csv(csv_file)
    st.dataframe(df)

    normalized_columns = [column.strip().lower() for column in df.columns]
    missing = [column for column in REQUIRED_COLUMNS if column not in normalized_columns]
    if missing:
        st.error(f"Missing required columns: {', '.join(missing)}")
        return

    df.columns = normalized_columns

    if not st.button("Start Batch"):
        return

    if max_delay < min_delay:
        st.error("Max delay must be >= min delay")
        return

    progress = st.progress(0)
    status_rows: list[dict] = []
    sent_count = 0

    resume_path = None
    if uploaded_resume is not None:
        resume_path = save_uploaded_resume(uploaded_resume)
    elif resume_path_input.strip():
        resume_path = resume_path_input.strip()

    total = len(df)
    for index, row in enumerate(df.to_dict(orient="records"), start=1):
        email = str(row.get("email", "")).strip()
        company = str(row.get("company", "")).strip()
        hr_name = str(row.get("hr_name", "Hiring Manager")).strip()
        position = str(row.get("position", "Role")).strip()

        subject = str(
            config.get("default_subject", "Application for {position} - {candidate_name}")
        ).format(position=position, candidate_name=config.get("candidate_name", ""))
        body = render_body(template, config, hr_name, company, position)

        if already_sent_today(email):
            status = "Skipped"
            reason = "Duplicate same day"
        elif sent_count >= int(daily_max):
            status = "Skipped"
            reason = "Daily max reached"
        elif dry_run:
            status = "DryRun"
            reason = body[:120]
        else:
            ok, reason = send_email(
                hr_name,
                email,
                company,
                position,
                subject,
                body,
                resume_path,
            )
            status = "Sent" if ok else "Failed"
            if ok:
                sent_count += 1

        log_row(email, company, status, reason)
        status_rows.append(
            {
                "email": email,
                "company": company,
                "status": status,
                "reason": reason,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
            }
        )

        progress.progress(index / total)
        st.dataframe(pd.DataFrame(status_rows), use_container_width=True)

        if not dry_run and index < total:
            time.sleep(random.randint(int(min_delay), int(max_delay)))

    st.success("Batch complete.")


def main() -> None:
    ensure_files()
    config = load_config()
    template = load_template()

    st.title("Email Automation - Local Streamlit UI")

    sender = os.getenv("EMAIL_AUTOMATION_SENDER", "").strip()
    password = os.getenv("EMAIL_AUTOMATION_APP_PASSWORD", "").strip()
    if not sender or not password:
        st.error(
            "Set EMAIL_AUTOMATION_SENDER and EMAIL_AUTOMATION_APP_PASSWORD before sending emails."
        )

    single_tab, batch_tab = st.tabs(["Single Email", "Batch Email"])
    with single_tab:
        render_single_tab(config, template)
    with batch_tab:
        render_batch_tab(config, template)

    st.download_button(
        "Download sent log",
        data=LOG_PATH.read_bytes(),
        file_name="sent_log.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    main()
