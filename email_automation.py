#!/usr/bin/env python3
"""
HR Cold Email Automation System
Sends personalized cold emails to HR contacts with resume attachment
Features: Rate limiting, timing optimization, connection retry, AWS deployment ready
"""

import smtplib
import ssl
import time
import random
import logging
import pandas as pd
import os
import json
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Dict, Optional
import schedule
import holidays
from pathlib import Path

class EmailAutomationSystem:
    def __init__(self, config_file: str = 'config.json'):
        """Initialize the email automation system"""
        self.config = self.load_config(config_file)
        self.setup_logging()
        self.sent_today = 0
        self.daily_limit = self.config.get('daily_limit', 500)
        self.last_sent_date = datetime.now().date()
        self.smtp_server = None
        self.connection_attempts = 0
        self.max_connection_attempts = 3
        
    def load_config(self, config_file: str) -> Dict:
        """Load configuration from JSON file"""
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            # Create default config if not exists
            default_config = {
                "smtp_server": "smtp.gmail.com",
                "smtp_port": 587,
                "email": "your_email@gmail.com",
                "password": "your_app_password",
                "daily_limit": 500,
                "min_delay": 30,
                "max_delay": 120,
                "business_hours_start": 9,
                "business_hours_end": 18,
                "resume_path": "Abhinay-Kumar.pdf",
                "hr_contacts_file": "hr_contacts.csv",
                "email_template_file": "email_template.html",
                "sent_emails_log": "sent_emails.json",
                "country_code": "IN"
            }
            with open(config_file, 'w') as f:
                json.dump(default_config, f, indent=4)
            print(f"Created default config file: {config_file}")
            print("Please update the config file with your credentials and run again.")
            return default_config
    
    def setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('email_automation.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def load_hr_contacts(self) -> pd.DataFrame:
        """Load HR contacts from CSV file"""
        try:
            # Try different file formats
            file_path = self.config['hr_contacts_file']
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
            elif file_path.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(file_path)
            else:
                # Try to auto-detect
                try:
                    df = pd.read_csv(file_path)
                except:
                    df = pd.read_excel(file_path)
            
            # Standardize column names
            df.columns = df.columns.str.lower().str.strip()
            
            # Expected columns: company, hr_name, email, position
            required_columns = ['email']
            for col in required_columns:
                if col not in df.columns:
                    raise ValueError(f"Required column '{col}' not found in HR contacts file")
            
            self.logger.info(f"Loaded {len(df)} HR contacts")
            return df
            
        except Exception as e:
            self.logger.error(f"Error loading HR contacts: {e}")
            raise
    
    def load_email_template(self) -> str:
        """Load email template from file"""
        try:
            template_file = self.config['email_template_file']
            with open(template_file, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            # Create default template if not exists
            default_template = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .header { color: #2c3e50; }
        .content { margin: 20px 0; }
        .signature { margin-top: 30px; border-top: 1px solid #eee; padding-top: 20px; }
    </style>
</head>
<body>
    <div class="header">
        <h2>Subject: Application for Software Developer Position - {candidate_name}</h2>
    </div>
    
    <div class="content">
        <p>Dear {hr_name},</p>
        
        <p>I hope this email finds you well. I am writing to express my strong interest in software development opportunities at {company_name}.</p>
        
        <p>As a passionate software developer with expertise in Python, SQL, AWS, React, JavaScript, HTML, CSS, NumPy, and Pandas, I am excited about the possibility of contributing to your team's success. I have attached my resume for your review.</p>
        
        <p>Key highlights of my background:</p>
        <ul>
            <li>Strong programming skills in Python and JavaScript</li>
            <li>Experience with modern web technologies (React, HTML, CSS)</li>
            <li>Proficiency in data analysis tools (Pandas, NumPy)</li>
            <li>Cloud computing experience with AWS</li>
            <li>Database management skills with SQL</li>
        </ul>
        
        <p>I would welcome the opportunity to discuss how my skills and enthusiasm can contribute to {company_name}'s continued growth and success.</p>
        
        <p>Thank you for your time and consideration. I look forward to hearing from you.</p>
    </div>
    
    <div class="signature">
        <p>Best regards,<br>
        {candidate_name}<br>
        {phone_number}<br>
        {email_address}</p>
    </div>
</body>
</html>
            """
            
            with open(self.config['email_template_file'], 'w', encoding='utf-8') as f:
                f.write(default_template)
            
            self.logger.info(f"Created default email template: {self.config['email_template_file']}")
            return default_template
    
    def personalize_email(self, template: str, contact: Dict) -> tuple:
        """Personalize email template with contact information"""
        # Extract contact information
        company_name = contact.get('company', 'Your Company')
        hr_name = contact.get('hr_name', 'Hiring Manager')
        candidate_name = self.config.get('candidate_name', 'Abhinay Kumar')
        phone_number = self.config.get('phone_number', '+91-XXXXXXXXXX')
        email_address = self.config.get('email', 'your_email@gmail.com')
        
        # Personalize template
        personalized_content = template.format(
            company_name=company_name,
            hr_name=hr_name,
            candidate_name=candidate_name,
            phone_number=phone_number,
            email_address=email_address
        )
        
        # Extract subject from template or create default
        subject = f"Application for Developer Role – {candidate_name}"
        
        return subject, personalized_content
    
    def is_business_hours(self) -> bool:
        """Check if current time is within business hours"""
        now = datetime.now()
        current_hour = now.hour
        
        # Check if it's a weekend
        if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
        
        # Check if it's a holiday (Indian holidays)
        country_holidays = holidays.country_holidays(self.config.get('country_code', 'IN'))
        if now.date() in country_holidays:
            return False
        
        # Check business hours
        start_hour = self.config.get('business_hours_start', 9)
        end_hour = self.config.get('business_hours_end', 18)
        
        return start_hour <= current_hour < end_hour
    
    def wait_for_business_hours(self):
        """Wait until business hours if currently outside"""
        while not self.is_business_hours():
            self.logger.info("Outside business hours. Waiting...")
            time.sleep(3600)  # Wait 1 hour and check again
    
    def connect_smtp(self) -> bool:
        """Establish SMTP connection with retry logic"""
        try:
            if self.smtp_server:
                try:
                    # Test existing connection
                    self.smtp_server.noop()
                    return True
                except:
                    self.smtp_server = None
            
            self.logger.info("Establishing SMTP connection...")
            context = ssl.create_default_context()
            self.smtp_server = smtplib.SMTP(self.config['smtp_server'], self.config['smtp_port'])
            self.smtp_server.starttls(context=context)
            self.smtp_server.login(self.config['email'], self.config['password'])
            
            self.connection_attempts = 0
            self.logger.info("SMTP connection established successfully")
            return True
            
        except Exception as e:
            self.connection_attempts += 1
            self.logger.error(f"SMTP connection failed (attempt {self.connection_attempts}): {e}")
            
            if self.connection_attempts < self.max_connection_attempts:
                wait_time = 2 ** self.connection_attempts * 60  # Exponential backoff
                self.logger.info(f"Retrying connection in {wait_time} seconds...")
                time.sleep(wait_time)
                return self.connect_smtp()
            
            return False
    
    def send_email(self, contact: Dict, template: str) -> bool:
        """Send personalized email to a contact"""
        try:
            # Check daily limit
            if self.sent_today >= self.daily_limit:
                self.logger.warning(f"Daily limit of {self.daily_limit} emails reached")
                return False
            
            # Reset counter if new day
            if datetime.now().date() > self.last_sent_date:
                self.sent_today = 0
                self.last_sent_date = datetime.now().date()
            
            # Wait for business hours
            self.wait_for_business_hours()
            
            # Establish connection
            if not self.connect_smtp():
                self.logger.error("Failed to establish SMTP connection")
                return False
            
            # Create message
            msg = MIMEMultipart()
            subject, personalized_content = self.personalize_email(template, contact)
            
            msg['From'] = self.config['email']
            msg['To'] = contact['email']
            msg['Subject'] = subject
            
            # Add body
            msg.attach(MIMEText(personalized_content, 'html'))
            
            # Attach resume
            resume_path = self.config['resume_path']
            if os.path.exists(resume_path):
                with open(resume_path, 'rb') as attachment:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment.read())
                
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= {os.path.basename(resume_path)}'
                )
                msg.attach(part)
            
            # Send email
            text = msg.as_string()
            self.smtp_server.sendmail(self.config['email'], contact['email'], text)
            
            # Log success
            self.sent_today += 1
            self.logger.info(f"Email sent successfully to {contact['email']} ({contact.get('company', 'Unknown Company')})")
            
            # Save to sent log
            self.log_sent_email(contact, subject)
            
            # Random delay to avoid spam detection
            delay = random.randint(self.config.get('min_delay', 30), self.config.get('max_delay', 120))
            self.logger.info(f"Waiting {delay} seconds before next email...")
            time.sleep(delay)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send email to {contact['email']}: {e}")
            return False
    
    def log_sent_email(self, contact: Dict, subject: str):
        """Log sent email to JSON file"""
        log_file = self.config['sent_emails_log']
        
        # Load existing log
        sent_log = []
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r') as f:
                    sent_log = json.load(f)
            except:
                sent_log = []
        
        # Add new entry
        sent_log.append({
            'timestamp': datetime.now().isoformat(),
            'email': contact['email'],
            'company': contact.get('company', 'Unknown'),
            'hr_name': contact.get('hr_name', 'Unknown'),
            'subject': subject
        })
        
        # Save updated log
        with open(log_file, 'w') as f:
            json.dump(sent_log, f, indent=2)
    
    def get_unsent_contacts(self, contacts_df: pd.DataFrame) -> pd.DataFrame:
        """Filter out contacts that have already been sent emails"""
        log_file = self.config['sent_emails_log']
        
        if not os.path.exists(log_file):
            return contacts_df
        
        try:
            with open(log_file, 'r') as f:
                sent_log = json.load(f)
            
            sent_emails = {entry['email'] for entry in sent_log}
            unsent_contacts = contacts_df[~contacts_df['email'].isin(sent_emails)]
            
            self.logger.info(f"Found {len(unsent_contacts)} unsent contacts out of {len(contacts_df)} total")
            return unsent_contacts
            
        except Exception as e:
            self.logger.error(f"Error filtering sent contacts: {e}")
            return contacts_df
    
    def run_batch(self, batch_size: int = 50):
        """Run a batch of emails"""
        try:
            # Load contacts and template
            contacts_df = self.load_hr_contacts()
            template = self.load_email_template()
            
            # Filter unsent contacts
            unsent_contacts = self.get_unsent_contacts(contacts_df)
            
            if unsent_contacts.empty:
                self.logger.info("No unsent contacts found")
                return
            
            # Process batch
            batch_contacts = unsent_contacts.head(batch_size)
            success_count = 0
            
            for _, contact in batch_contacts.iterrows():
                if self.send_email(contact.to_dict(), template):
                    success_count += 1
                
                # Check daily limit
                if self.sent_today >= self.daily_limit:
                    self.logger.info("Daily limit reached. Stopping batch.")
                    break
            
            self.logger.info(f"Batch completed: {success_count}/{len(batch_contacts)} emails sent successfully")
            
        except Exception as e:
            self.logger.error(f"Error in batch processing: {e}")
        finally:
            if self.smtp_server:
                try:
                    self.smtp_server.quit()
                except:
                    pass
    
    def run_continuous(self):
        """Run continuous email sending with scheduling"""
        self.logger.info("Starting continuous email automation...")
        
        # Schedule batches throughout business hours
        schedule.every().day.at("09:00").do(lambda: self.run_batch(20))
        schedule.every().day.at("11:00").do(lambda: self.run_batch(20))
        schedule.every().day.at("14:00").do(lambda: self.run_batch(20))
        schedule.every().day.at("16:00").do(lambda: self.run_batch(20))
        
        while True:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except KeyboardInterrupt:
                self.logger.info("Stopping email automation...")
                break
            except Exception as e:
                self.logger.error(f"Error in continuous mode: {e}")
                time.sleep(300)  # Wait 5 minutes before retry

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='HR Cold Email Automation System')
    parser.add_argument('--batch-size', type=int, default=50, help='Number of emails per batch')
    parser.add_argument('--continuous', action='store_true', help='Run in continuous mode')
    parser.add_argument('--config', default='config.json', help='Configuration file path')
    
    args = parser.parse_args()
    
    # Initialize system
    email_system = EmailAutomationSystem(args.config)
    
    if args.continuous:
        email_system.run_continuous()
    else:
        email_system.run_batch(args.batch_size)

if __name__ == "__main__":
    main()
