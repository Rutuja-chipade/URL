import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import get_settings

settings = get_settings()

async def send_reset_password_email(email: str, reset_link: str):
    """Send a real password reset email using SMTP."""
    
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        print("[WARN] SMTP not configured. Falling back to demo mode.")
        return False

    # Create full reset URL
    full_link = f"{settings.BASE_URL}{reset_link}"
    
    # Email content
    subject = "Reset Your Shortify Pro Password"
    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
            <h2 style="color: #8a2be2;">Password Reset Request</h2>
            <p>Hello,</p>
            <p>We received a request to reset your password for your Shortify Pro account. Click the button below to set a new password:</p>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{full_link}" style="background-color: #8a2be2; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold;">Reset Password</a>
            </div>
            <p>If you did not request this, you can safely ignore this email.</p>
            <p>This link will expire in 1 hour.</p>
            <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
            <p style="font-size: 12px; color: #888;">© 2024 Shortify Pro – Professional URL Management</p>
        </div>
    </body>
    </html>
    """

    message = MIMEMultipart()
    message["From"] = settings.SMTP_FROM_EMAIL or settings.SMTP_USER
    message["To"] = email
    message["Subject"] = subject
    message.attach(MIMEText(body, "html"))

    try:
        # Use a separate thread or non-blocking way in production, 
        # but for this script we'll do standard smtplib (wrapped in async for interface)
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(message)
        print(f"[OK] Password reset email sent to {email}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to send email: {e}")
        return False
