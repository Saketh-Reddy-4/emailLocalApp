#!/usr/bin/env python3
"""
HR Cold Email Automation System - 24x7 Version
Sends emails without business hour restrictions, optimized for 400 emails/day
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
from pathlib import Path

class EmailAutomation24x7:
    def __init__(self, config_file: str = 'config.json'):
        """Initialize the 24x7 email automation system"""
        self.config = self.load_config(config_file)
        self.setup_logging()
        self.sent_today = 0
        self.daily_limit = self.config.get('daily_limit', 400)
        self.last_sent_date = datetime.now().date()
        self.smtp_server = None
        self.connection_attempts = 0
        self.max_connection_attempts = 3
        
        # Calculate optimal timing for 400 emails in 24 hours
        # 400 emails / 24 hours = ~16.67 emails per hour
        # That's about 3.6 minutes (216 seconds) between emails on average
        self.optimal_interval = (24 * 60 * 60) // self.daily_limit  # seconds between emails
        print(f"📊 Optimal interval: {self.optimal_interval} seconds (~{self.optimal_interval/60:.1f} minutes) between emails")
        
    def load_config(self, config_file: str) -> Dict:
        """Load configuration from JSON file"""
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Config file not found: {config_file}")
    
    def setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('email_automation_24x7.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def load_hr_contacts(self) -> pd.DataFrame:
        """Load HR contacts from CSV file"""
        try:
            file_path = self.config['hr_contacts_file']
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
            elif file_path.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(file_path)
            else:
                df = pd.read_csv(file_path)
            
            df.columns = df.columns.str.lower().str.strip()
            
            if 'email' not in df.columns:
                raise ValueError("Required column 'email' not found in HR contacts file")
            
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
        except Exception as e:
            self.logger.error(f"Error loading email template: {e}")
            raise
    
    def personalize_email(self, template: str, contact: Dict) -> tuple:
        """Personalize email template with contact information"""
        company_name = contact.get('company', 'Your Company')
        hr_name = contact.get('hr_name', 'Hiring Manager')
        candidate_name = self.config.get('candidate_name', 'Abhinay Kumar')
        phone_number = self.config.get('phone_number', '+91-XXXXXXXXXX')
        email_address = self.config.get('email', 'your_email@gmail.com')
        
        personalized_content = template.format(
            company_name=company_name,
            hr_name=hr_name,
            candidate_name=candidate_name,
            phone_number=phone_number,
            email_address=email_address
        )
        
        subject = f"Application for Developer Role – {candidate_name}"
        
        return subject, personalized_content
    
    def connect_smtp(self) -> bool:
        """Establish SMTP connection with retry logic"""
        try:
            # Always create fresh connection to avoid timeout issues
            if self.smtp_server:
                try:
                    self.smtp_server.quit()
                except:
                    pass
                self.smtp_server = None
            
            self.logger.info("Establishing fresh SMTP connection...")
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
                wait_time = min(300, 2 ** self.connection_attempts * 60)  # Cap at 5 minutes
                self.logger.info(f"Retrying connection in {wait_time} seconds...")
                time.sleep(wait_time)
                return self.connect_smtp()
            
            return False
    
    def calculate_smart_delay(self) -> int:
        """Calculate smart delay based on daily progress and remaining time"""
        now = datetime.now()
        
        # Reset counter if new day
        if now.date() > self.last_sent_date:
            self.sent_today = 0
            self.last_sent_date = now.date()
        
        # If we've hit the daily limit, wait until next day
        if self.sent_today >= self.daily_limit:
            next_day = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            wait_seconds = (next_day - now).total_seconds()
            self.logger.info(f"Daily limit reached ({self.daily_limit}). Waiting {wait_seconds/3600:.1f} hours until next day.")
            return int(wait_seconds)
        
        # Calculate remaining emails and time today
        remaining_emails = self.daily_limit - self.sent_today
        end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        remaining_seconds = (end_of_day - now).total_seconds()
        
        # Calculate optimal delay
        if remaining_emails > 0:
            optimal_delay = remaining_seconds / remaining_emails
            # Add some randomization (±25%) to avoid patterns
            min_delay = max(30, optimal_delay * 0.75)  # Minimum 30 seconds
            max_delay = min(300, optimal_delay * 1.25)  # Maximum 5 minutes
            
            # Ensure min_delay is not greater than max_delay
            if min_delay >= max_delay:
                min_delay = 30
                max_delay = 120
            
            delay = random.randint(int(min_delay), int(max_delay))
            
            self.logger.info(f"Progress: {self.sent_today}/{self.daily_limit} emails sent today")
            self.logger.info(f"Remaining: {remaining_emails} emails in {remaining_seconds/3600:.1f} hours")
            
            return delay
        
        return 60  # Default 1 minute
    
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
                self.logger.info("New day started - reset email counter")
            
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
            self.logger.info(f"Daily progress: {self.sent_today}/{self.daily_limit} emails sent")
            
            # Save to sent log
            self.log_sent_email(contact, subject)
            
            # Calculate smart delay
            delay = self.calculate_smart_delay()
            if delay > 60:  # If delay is more than 1 minute, show countdown
                self.logger.info(f"Next email in {delay} seconds ({delay/60:.1f} minutes)")
            else:
                self.logger.info(f"Next email in {delay} seconds")
            
            time.sleep(delay)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send email to {contact['email']}: {e}")
            return False
    
    def log_sent_email(self, contact: Dict, subject: str):
        """Log sent email to JSON file"""
        log_file = self.config['sent_emails_log']
        
        sent_log = []
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r') as f:
                    sent_log = json.load(f)
            except:
                sent_log = []
        
        sent_log.append({
            'timestamp': datetime.now().isoformat(),
            'email': contact['email'],
            'company': contact.get('company', 'Unknown'),
            'hr_name': contact.get('hr_name', 'Unknown'),
            'subject': subject
        })
        
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
    
    def run_continuous(self):
        """Run continuous email sending - 24x7 operation"""
        self.logger.info("Starting 24x7 email automation...")
        self.logger.info(f"Daily limit: {self.daily_limit} emails")
        self.logger.info(f"Target: Complete 1,838 contacts in ~{1838/self.daily_limit:.1f} days")
        
        try:
            # Load contacts and template
            contacts_df = self.load_hr_contacts()
            template = self.load_email_template()
            
            while True:
                try:
                    # Get unsent contacts
                    unsent_contacts = self.get_unsent_contacts(contacts_df)
                    
                    if unsent_contacts.empty:
                        self.logger.info("🎉 All emails have been sent! Campaign completed.")
                        break
                    
                    # Check if we've reached daily limit
                    if self.sent_today >= self.daily_limit:
                        # Wait until next day
                        now = datetime.now()
                        next_day = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                        wait_seconds = (next_day - now).total_seconds()
                        self.logger.info(f"Daily limit reached. Sleeping until next day ({wait_seconds/3600:.1f} hours)")
                        time.sleep(wait_seconds)
                        continue
                    
                    # Send next email
                    next_contact = unsent_contacts.iloc[0]
                    success = self.send_email(next_contact.to_dict(), template)
                    
                    if not success:
                        # If sending failed, wait a bit longer before retry
                        self.logger.info("Email sending failed. Waiting 5 minutes before retry...")
                        time.sleep(300)
                
                except KeyboardInterrupt:
                    self.logger.info("Stopping email automation (Ctrl+C pressed)...")
                    break
                except Exception as e:
                    self.logger.error(f"Error in continuous mode: {e}")
                    self.logger.info("Waiting 5 minutes before retry...")
                    time.sleep(300)
        
        finally:
            if self.smtp_server:
                try:
                    self.smtp_server.quit()
                except:
                    pass
            
            self.logger.info("Email automation stopped.")

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='HR Cold Email Automation System - 24x7 Version')
    parser.add_argument('--config', default='config.json', help='Configuration file path')
    
    args = parser.parse_args()
    
    # Initialize system
    email_system = EmailAutomation24x7(args.config)
    
    # Run continuous mode
    email_system.run_continuous()

if __name__ == "__main__":
    main()
