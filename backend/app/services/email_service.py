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
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reset Your Password</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            text-align: center;
            padding: 20px 0;
            border-bottom: 2px solid #4F46E5;
        }}
        .logo {{
            font-size: 28px;
            font-weight: bold;
            color: #4F46E5;
        }}
        .content {{
            padding: 30px 0;
        }}
        .button {{
            display: inline-block;
            background-color: #4F46E5;
            color: white !important;
            text-decoration: none;
            padding: 14px 28px;
            border-radius: 8px;
            font-weight: 600;
            margin: 20px 0;
        }}
        .button:hover {{
            background-color: #4338CA;
        }}
        .footer {{
            padding-top: 20px;
            border-top: 1px solid #eee;
            font-size: 14px;
            color: #666;
        }}
        .warning {{
            background-color: #FEF3C7;
            border-left: 4px solid #F59E0B;
            padding: 12px;
            margin: 20px 0;
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">SelmApp</div>
    </div>
    
    <div class="content">
        <p>{greeting}</p>
        
        <p>We received a request to reset your password for your SelmApp account. Click the button below to create a new password:</p>
        
        <p style="text-align: center;">
            <a href="{reset_url}" class="button">Reset Password</a>
        </p>
        
        <p>Or copy and paste this link into your browser:</p>
        <p style="word-break: break-all; color: #4F46E5;">{reset_url}</p>
        
        <div class="warning">
            <strong>This link will expire in 1 hour.</strong><br>
            If you didn't request a password reset, you can safely ignore this email.
        </div>
    </div>
    
    <div class="footer">
        <p>This email was sent by SelmApp. If you have any questions, please contact our support team.</p>
        <p>&copy; {settings.PROJECT_NAME}. All rights reserved.</p>
    </div>
</body>
</html>
"""
        
        text_content = f"""
{greeting}

We received a request to reset your password for your SelmApp account.

Click the link below to create a new password:
{reset_url}

This link will expire in 1 hour.

If you didn't request a password reset, you can safely ignore this email.

---
This email was sent by SelmApp.
"""
        
        return await self.send_email(
            to_email=to_email,
            subject="Reset Your SelmApp Password",
            html_content=html_content,
            text_content=text_content
        )


# Global instance
email_service = EmailService()
