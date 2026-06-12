"""Email service for sending password reset emails via Gmail SMTP."""

import smtplib
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import get_settings

settings = get_settings()


def _is_smtp_configured() -> bool:
    """Check if SMTP is actually configured with real credentials."""
    user = settings.SMTP_USER
    pwd = settings.SMTP_PASSWORD

    # Log current state for debugging in production
    if user:
        print(f"[SMTP] SMTP_USER is set: {user}")
    else:
        print("[SMTP] SMTP_USER is NOT set or empty")

    if pwd:
        # Remove spaces Google sometimes shows in app passwords
        cleaned = pwd.replace(" ", "")
        print(f"[SMTP] SMTP_PASSWORD is set (length: {len(cleaned)})")
    else:
        print("[SMTP] SMTP_PASSWORD is NOT set or empty")

    if not user or user.strip() in ("", "your-email@gmail.com"):
        return False
    if not pwd or pwd.strip() in ("", "your-app-password"):
        return False
    return True


def _send_email_sync(to_email: str, subject: str, html_body: str) -> bool:
    """Send an email synchronously using SMTP (called in a thread)."""
    # Strip spaces from password (Google sometimes shows it with spaces)
    smtp_password = (settings.SMTP_PASSWORD or "").replace(" ", "")
    smtp_user = (settings.SMTP_USER or "").strip()
    from_email = (settings.SMTP_FROM_EMAIL or smtp_user).strip()

    message = MIMEMultipart()
    message["From"] = from_email
    message["To"] = to_email
    message["Subject"] = subject
    message.attach(MIMEText(html_body, "html"))

    try:
        print(f"[SMTP] Connecting to smtp.gmail.com:587 as {smtp_user}...")
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_user, smtp_password)
            server.send_message(message)
        print(f"[SMTP] ✅ Email sent successfully to {to_email}")
        return True
    except smtplib.SMTPAuthenticationError as e:
        print(f"[SMTP] ❌ Authentication failed for {smtp_user}: {e}")
        print("[SMTP] Make sure SMTP_PASSWORD is a valid 16-char Google App Password (no spaces)")
        return False
    except smtplib.SMTPException as e:
        print(f"[SMTP] ❌ SMTP Error sending to {to_email}: {e}")
        return False
    except Exception as e:
        print(f"[SMTP] ❌ Unexpected error sending to {to_email}: {type(e).__name__}: {e}")
        return False


async def send_reset_password_email(to_email: str, reset_link: str, base_url: str = None) -> bool:
    """Send a password reset email to a user.

    Args:
        to_email: The recipient's email address.
        reset_link: The reset password link path (e.g., /reset-password?token=abc123).
        base_url: The actual base URL from the request (e.g., https://your-app.onrender.com).

    Returns:
        True if email was sent successfully, False otherwise.
    """
    if not _is_smtp_configured():
        print("[SMTP] ⚠️  SMTP not configured. Set SMTP_USER and SMTP_PASSWORD in environment variables.")
        print("[SMTP] ⚠️  Falling back to demo mode (reset link shown on screen).")
        return False

    # Build the full reset URL using actual request URL (not localhost)
    base = (base_url or settings.BASE_URL or "").rstrip("/")
    full_link = f"{base}{reset_link}"
    print(f"[SMTP] Sending password reset to {to_email} — link: {full_link}")

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

    try:
        result = await asyncio.to_thread(_send_email_sync, to_email, subject, html_body)
        return result
    except Exception as e:
        print(f"[SMTP] ❌ Failed to dispatch email thread: {e}")
        return False
