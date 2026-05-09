"""Email service for sending password reset emails via Gmail SMTP."""

import smtplib
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import get_settings

settings = get_settings()

# Placeholder values that should NOT be treated as real credentials
_PLACEHOLDER_VALUES = {"your-email@gmail.com", "your-app-password", "", None}


def _is_smtp_configured() -> bool:
    """Check if SMTP is actually configured with real credentials."""
    if settings.SMTP_USER in _PLACEHOLDER_VALUES:
        return False
    if settings.SMTP_PASSWORD in _PLACEHOLDER_VALUES:
        return False
    return True


def _send_email_sync(to_email: str, subject: str, html_body: str) -> bool:
    """Send an email synchronously using SMTP (called in a thread)."""
    message = MIMEMultipart()
    message["From"] = settings.SMTP_FROM_EMAIL or settings.SMTP_USER
    message["To"] = to_email
    message["Subject"] = subject
    message.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(message)
        print(f"[OK] Email sent to {to_email}")
        return True
    except smtplib.SMTPAuthenticationError:
        print(f"[ERROR] SMTP Authentication failed. Check your SMTP_USER and SMTP_PASSWORD in .env")
        return False
    except smtplib.SMTPException as e:
        print(f"[ERROR] SMTP Error sending email to {to_email}: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error sending email to {to_email}: {e}")
        return False


async def send_reset_password_email(to_email: str, reset_link: str) -> bool:
    """Send a password reset email to a user.
    
    Args:
        to_email: The recipient's email address (the user who forgot their password).
        reset_link: The reset password link path (e.g., /reset-password?token=abc123).
    
    Returns:
        True if email was sent successfully, False otherwise.
    """
    if not _is_smtp_configured():
        print("[WARN] SMTP not configured. Update SMTP_USER and SMTP_PASSWORD in your .env file.")
        print("[WARN] Falling back to demo mode (reset link will be shown in browser console).")
        return False

    # Build the full reset URL
    full_link = f"{settings.BASE_URL}{reset_link}"

    subject = "Reset Your Shortify Pro Password"
    html_body = f"""
    <html>
    <body style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333; background-color: #f4f4f4; margin: 0; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; padding: 30px; background: #ffffff; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.08);">
            <div style="text-align: center; margin-bottom: 30px;">
                <div style="font-size: 2rem;">⚡</div>
                <h1 style="color: #7c3aed; margin: 10px 0 0 0; font-size: 1.5rem;">Shortify Pro</h1>
            </div>
            
            <h2 style="color: #1e293b; font-size: 1.3rem; margin-bottom: 16px;">Password Reset Request</h2>
            <p>Hello,</p>
            <p>We received a request to reset your password for your <strong>Shortify Pro</strong> account associated with <strong>{to_email}</strong>.</p>
            <p>Click the button below to set a new password:</p>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="{full_link}" style="background: linear-gradient(135deg, #7c3aed 0%, #0ea5e9 100%); color: white; padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: bold; font-size: 1rem; display: inline-block;">
                    Reset My Password
                </a>
            </div>
            
            <p style="font-size: 0.9rem; color: #64748b;">If the button doesn't work, copy and paste this link into your browser:</p>
            <p style="font-size: 0.85rem; color: #7c3aed; word-break: break-all;">{full_link}</p>
            
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0;">
            
            <p style="font-size: 0.85rem; color: #94a3b8;">If you did not request this password reset, you can safely ignore this email. Your password will not change.</p>
            <p style="font-size: 0.85rem; color: #94a3b8;">This link will expire in <strong>1 hour</strong>.</p>
            
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0;">
            <p style="font-size: 0.75rem; color: #cbd5e1; text-align: center;">© 2024 Shortify Pro – Professional URL Management</p>
        </div>
    </body>
    </html>
    """

    # Run the synchronous SMTP call in a thread so it doesn't block the event loop
    try:
        result = await asyncio.to_thread(_send_email_sync, to_email, subject, html_body)
        return result
    except Exception as e:
        print(f"[ERROR] Failed to send email: {e}")
        return False
