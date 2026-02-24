# email-automation (Local Streamlit UI)

This repository is a **local-only** email automation tool with a minimal Streamlit wrapper.

## File Tree

```text
email-automation/
├── app.py
├── email_automation.py
├── email_automation_24x7.py
├── config.json
├── email_template.txt
├── requirements.txt
├── README.md
└── logs/
```

## Environment Variables (required for sending)

```bash
export EMAIL_AUTOMATION_SENDER="your_email@gmail.com"
export EMAIL_AUTOMATION_APP_PASSWORD="your_gmail_app_password"
```

If these are missing, the UI refuses to send.

## UI Features

- **Single Email tab**
  - Inputs: name, email, company, position, subject, resume upload/path
  - Send one email
- **Batch Email tab**
  - Upload CSV with columns: `company, hr_name, email, position`
  - Controls: min delay, max delay, daily max, dry run
  - Start batch and view statuses
- Duplicate prevention via `logs/sent_log.csv` for same-day sends

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```
