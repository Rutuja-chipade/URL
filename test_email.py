"""Test SMTP email directly."""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "rutujachipade65@gmail.com"
SMTP_PASSWORD = "sdcradadybreogdd"

print(f"Testing SMTP with user: {SMTP_USER}")
print(f"Password length: {len(SMTP_PASSWORD)}")

try:
    msg = MIMEMultipart()
    msg["From"] = SMTP_USER
    msg["To"] = SMTP_USER  # Send to self for test
    msg["Subject"] = "Shortify Pro - SMTP Test"
    msg.attach(MIMEText("<h1>Email is working!</h1>", "html"))

    print("Connecting to smtp.gmail.com:587...")
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
        server.set_debuglevel(1)
        server.ehlo()
        server.starttls()
        server.ehlo()
        print(f"Logging in as {SMTP_USER}...")
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
    print("\n[SUCCESS] Email sent! Check your inbox.")
except smtplib.SMTPAuthenticationError as e:
    print(f"\n[ERROR] Authentication failed: {e}")
    print("\nFIX: Your Google App Password is wrong or expired.")
    print("Steps to regenerate:")
    print("1. Go to https://myaccount.google.com/apppasswords")
    print("2. Delete the old password for 'Shortify Pro'")
    print("3. Create a new App Password")
    print("4. Copy the 16-character code (no spaces)")
except Exception as e:
    print(f"\n[ERROR] {type(e).__name__}: {e}")
