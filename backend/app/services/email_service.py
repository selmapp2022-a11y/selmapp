"""
Email service for sending transactional emails (password reset, verification, etc.)
"""
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails via SMTP"""
    
    def __init__(self):
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
        self.from_email = settings.SMTP_USER or "noreply@selmapp.com"
        self.from_name = "SelmApp"
    
    def _is_configured(self) -> bool:
        """Check if email service is properly configured"""
        return bool(self.smtp_host and self.smtp_user and self.smtp_password)
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """
        Send an email.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML content of the email
            text_content: Plain text fallback (optional)
            
        Returns:
            True if email was sent successfully, False otherwise
        """
        if not self._is_configured():
            logger.warning(
                f"Email service not configured. Would have sent email to {to_email}: {subject}"
            )
            # In development, log the email content for testing
            logger.info(f"Email HTML content:\n{html_content}")
            return True  # Return True in dev to not block the flow
        
        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.from_name} <{self.from_email}>"
            msg["To"] = to_email
            
            # Add text/plain part
            if text_content:
                part1 = MIMEText(text_content, "plain")
                msg.attach(part1)
            
            # Add text/html part
            part2 = MIMEText(html_content, "html")
            msg.attach(part2)
            
            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.from_email, to_email, msg.as_string())
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False
    
    async def send_password_reset_email(
        self,
        to_email: str,
        reset_token: str,
        user_name: Optional[str] = None
    ) -> bool:
        """
        Send a password reset email.
        
        Args:
            to_email: User's email address
            reset_token: Password reset token
            user_name: User's name (optional)
            
        Returns:
            True if email was sent successfully
        """
        # Build reset URL - this should point to your frontend
        reset_url = f"{settings.PUBLIC_BASE_URL}/reset-password?token={reset_token}"

        greeting = f"Hi {user_name}," if user_name else "Hi,"

        # Brand v1.0 (2026) palette:
        #   Navy primary  = #183048
        #   Teal accent   = #5EEAD4
        #   Ink secondary = #4A5568
        # Logo is rendered with pure HTML/CSS (rounded Navy square + white "S"
        # initial + "SELM" wordmark) instead of an image so it survives email
        # clients that block remote images by default. This matches the
        # selmapp.ca / selmapp.com lockup.
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reset Your SELM Password</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #1A202C;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
            background-color: #FFFFFF;
        }}
        .header {{
            text-align: center;
            padding: 28px 0 20px;
            border-bottom: 2px solid #183048;
        }}
        .logo-lockup {{
            display: inline-block;
            text-align: left;
            line-height: 1;
        }}
        .logo-row {{
            display: inline-block;
            vertical-align: middle;
        }}
        .logo-symbol {{
            display: inline-block;
            vertical-align: middle;
            width: 56px;
            height: 56px;
            background-color: #183048;
            border-radius: 14px;
            color: #FFFFFF;
            font-family: Georgia, 'Times New Roman', serif;
            font-size: 36px;
            font-weight: 700;
            line-height: 56px;
            text-align: center;
            margin-right: 14px;
        }}
        .logo-text {{
            display: inline-block;
            vertical-align: middle;
        }}
        .logo-wordmark {{
            font-size: 26px;
            font-weight: 800;
            color: #183048;
            letter-spacing: 0.5px;
            line-height: 1;
        }}
        .logo-tagline {{
            font-size: 11px;
            color: #5EEAD4;
            letter-spacing: 2px;
            margin-top: 4px;
            font-weight: 600;
        }}
        .content {{
            padding: 30px 4px;
            color: #1A202C;
        }}
        .button {{
            display: inline-block;
            background-color: #183048;
            color: #FFFFFF !important;
            text-decoration: none;
            padding: 14px 28px;
            border-radius: 10px;
            font-weight: 600;
            margin: 20px 0;
        }}
        .button:hover {{
            background-color: #0F1F30;
        }}
        .link-text {{
            word-break: break-all;
            color: #183048;
        }}
        .footer {{
            padding-top: 20px;
            border-top: 1px solid #E2E8F0;
            font-size: 13px;
            color: #718096;
        }}
        .warning {{
            background-color: #F0FDFA;
            border-left: 4px solid #5EEAD4;
            padding: 12px 16px;
            margin: 24px 0;
            border-radius: 4px;
            color: #134E4A;
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="logo-lockup">
            <div class="logo-row">
                <span class="logo-symbol">S</span>
                <span class="logo-text">
                    <div class="logo-wordmark">SELM</div>
                    <div class="logo-tagline">ENGLISH, SIMPLY</div>
                </span>
            </div>
        </div>
    </div>

    <div class="content">
        <p>{greeting}</p>

        <p>We received a request to reset the password on your SELM account. Click the button below to choose a new password:</p>

        <p style="text-align: center;">
            <a href="{reset_url}" class="button">Reset password</a>
        </p>

        <p>Or copy and paste this link into your browser:</p>
        <p class="link-text">{reset_url}</p>

        <div class="warning">
            <strong>This link will expire in 1 hour.</strong><br>
            If you didn't request a password reset, you can safely ignore this email — your password won't change.
        </div>
    </div>

    <div class="footer">
        <p>This message was sent by SELM. Questions? Reply to this email or visit <a href="https://selmapp.ca" style="color:#183048;">selmapp.ca</a>.</p>
        <p>&copy; SELM — English, simply.</p>
    </div>
</body>
</html>
"""

        text_content = f"""
{greeting}

We received a request to reset the password on your SELM account.

Click the link below to choose a new password:
{reset_url}

This link will expire in 1 hour.

If you didn't request a password reset, you can safely ignore this email — your password won't change.

---
SELM — English, simply.
https://selmapp.ca
"""

        return await self.send_email(
            to_email=to_email,
            subject="Reset your SELM password",
            html_content=html_content,
            text_content=text_content
        )


# Global instance
email_service = EmailService()
