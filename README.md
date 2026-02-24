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
├── .env.example
└── logs/
    └── sent_log.csv
```

## Sender credentials (local `.env` or OS environment)

The app reads sender credentials from either your shell environment or a local `.env` file.

Supported keys:

- `EMAIL_AUTOMATION_SENDER`
- `EMAIL_AUTOMATION_APP_PASSWORD`

Precedence behavior:

- Existing OS environment variables win.
- `.env` values are used only when OS environment variables are not already set.

Create your local `.env` file from the example:

```bash
cp .env.example .env
```

Then edit `.env` and set your real values:

```env
EMAIL_AUTOMATION_SENDER=your_email@gmail.com
EMAIL_AUTOMATION_APP_PASSWORD=your_gmail_app_password
```

> `.env` is gitignored to avoid committing secrets.

## UI Features

- **Single Email tab**
  - Inputs: name, email, company, position, subject, resume upload/path
  - Shows template preview before send
  - Sends plain-text email
- **Batch Email tab**
  - Upload CSV with columns: `company, hr_name, email, position`
  - Controls: min delay, max delay, daily max, dry run
  - Duplicate skip log in `logs/sent_log.csv`

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```
