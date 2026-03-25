"""Email service — sends transactional emails directly from our domain.
Direct SMTP delivery to recipient's mail server. No third-party services.
Some emails may land in spam — that's expected for MVP.
"""
import smtplib
import socket
import dns.resolver
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import APP_URL

FROM_EMAIL = os.getenv("FROM_EMAIL", "hello@reviewrep.me")
FROM_NAME = os.getenv("FROM_NAME", "ReviewRep")


def _get_mx_host(domain: str) -> str:
    """Get the MX server for a domain."""
    try:
        records = dns.resolver.resolve(domain, "MX")
        mx = sorted(records, key=lambda r: r.preference)
        return str(mx[0].exchange).rstrip(".")
    except Exception:
        return f"mail.{domain}"


def send_email(to: str, subject: str, html_body: str) -> bool:
    """Send email directly to recipient's mail server."""
    msg = MIMEMultipart("alternative")
    msg["From"] = f"{FROM_NAME} <{FROM_EMAIL}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg["Reply-To"] = "stan.evodek@gmail.com"
    msg.attach(MIMEText(html_body, "html"))

    try:
        recipient_domain = to.split("@")[1]
        mx_host = _get_mx_host(recipient_domain)

        with smtplib.SMTP(mx_host, 25, timeout=10) as server:
            server.ehlo("reviewrep.me")
            try:
                server.starttls()
                server.ehlo("reviewrep.me")
            except Exception:
                pass
            server.sendmail(FROM_EMAIL, to, msg.as_string())

        print(f"[EMAIL SENT] To: {to} Subject: {subject}")
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] To: {to} Error: {e}")
        return False


# --- Email Templates ---

def _base_template(content: str) -> str:
    return f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 560px; margin: 0 auto; padding: 40px 20px;">
        <div style="margin-bottom: 32px;">
            <span style="font-size: 18px; font-weight: 700; color: #111;">Review</span><span style="font-size: 18px; font-weight: 700; color: #2563eb;">Rep</span>
        </div>
        {content}
        <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #e5e7eb; font-size: 12px; color: #9ca3af;">
            <p style="background: #fef3c7; padding: 8px 12px; border-radius: 6px; color: #92400e; margin-bottom: 12px;">Can't find this email? Please check your spam or junk folder.</p>
            <p>ReviewRep · Canterbury, UK</p>
            <p>You received this email because you signed up at reviewrep.me</p>
        </div>
    </div>
    """


def send_verification_email(to: str, name: str, token: str) -> bool:
    verify_url = f"{APP_URL}/verify-email?token={token}"
    html = _base_template(f"""
        <h2 style="font-size: 22px; color: #111; margin-bottom: 8px;">Verify your email</h2>
        <p style="color: #6b7280; font-size: 15px; line-height: 1.6;">
            Hi {name},<br><br>
            Thanks for signing up for ReviewReply AI. Please verify your email address to get started.
        </p>
        <a href="{verify_url}"
           style="display: inline-block; margin-top: 20px; background: #2563eb; color: #fff; padding: 12px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 15px;">
            Verify Email Address
        </a>
        <p style="margin-top: 20px; font-size: 13px; color: #9ca3af;">
            Or copy this link: {verify_url}
        </p>
    """)
    return send_email(to, "Verify your email — ReviewReply AI", html)


def send_welcome_email(to: str, name: str) -> bool:
    html = _base_template(f"""
        <h2 style="font-size: 22px; color: #111; margin-bottom: 8px;">Welcome to ReviewReply AI</h2>
        <p style="color: #6b7280; font-size: 15px; line-height: 1.6;">
            Hi {name},<br><br>
            Your 7-day free trial has started. Here's how to get the most out of it:
        </p>
        <ol style="color: #374151; font-size: 15px; line-height: 2; padding-left: 20px;">
            <li><strong>Add your business</strong> — name, location, and response tone</li>
            <li><strong>Add a review</strong> — paste one from Google to test</li>
            <li><strong>Generate a response</strong> — see AI write a reply in your brand's voice</li>
            <li><strong>Approve or edit</strong> — you're always in control</li>
        </ol>
        <a href="{APP_URL}/dashboard"
           style="display: inline-block; margin-top: 20px; background: #2563eb; color: #fff; padding: 12px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 15px;">
            Go to Dashboard
        </a>
        <p style="margin-top: 24px; color: #6b7280; font-size: 14px;">
            Questions? Just reply to this email — we read every message.
        </p>
    """)
    return send_email(to, f"Welcome to ReviewReply AI, {name}!", html)


def send_trial_ending_email(to: str, name: str, days_left: int) -> bool:
    html = _base_template(f"""
        <h2 style="font-size: 22px; color: #111; margin-bottom: 8px;">Your trial ends in {days_left} day{'s' if days_left != 1 else ''}</h2>
        <p style="color: #6b7280; font-size: 15px; line-height: 1.6;">
            Hi {name},<br><br>
            Your free trial of ReviewReply AI is almost over. To keep your AI review responses running, choose a plan:
        </p>
        <div style="margin: 24px 0; padding: 20px; background: #f9fafb; border-radius: 12px; border: 1px solid #e5e7eb;">
            <p style="margin: 0 0 8px; font-weight: 600; color: #111;">Starter — £19/mo</p>
            <p style="margin: 0; font-size: 14px; color: #6b7280;">50 responses/month, 1 location</p>
        </div>
        <div style="margin: 0 0 24px; padding: 20px; background: #eff6ff; border-radius: 12px; border: 1px solid #bfdbfe;">
            <p style="margin: 0 0 8px; font-weight: 600; color: #111;">Pro — £39/mo</p>
            <p style="margin: 0; font-size: 14px; color: #6b7280;">Unlimited responses, 3 locations, analytics</p>
        </div>
        <a href="{APP_URL}/pricing"
           style="display: inline-block; background: #2563eb; color: #fff; padding: 12px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 15px;">
            Choose a Plan
        </a>
    """)
    return send_email(to, f"Your ReviewReply AI trial ends in {days_left} days", html)


def send_new_review_notification(to: str, name: str, business_name: str, reviewer: str, rating: int) -> bool:
    stars = "★" * rating + "☆" * (5 - rating)
    html = _base_template(f"""
        <h2 style="font-size: 22px; color: #111; margin-bottom: 8px;">New review for {business_name}</h2>
        <p style="color: #6b7280; font-size: 15px; line-height: 1.6;">
            Hi {name},<br><br>
            <strong>{reviewer}</strong> just left a <span style="color: #f59e0b;">{stars}</span> review.
            An AI response is ready for your approval.
        </p>
        <a href="{APP_URL}/dashboard"
           style="display: inline-block; margin-top: 20px; background: #2563eb; color: #fff; padding: 12px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 15px;">
            Review & Approve
        </a>
    """)
    return send_email(to, f"New {rating}-star review for {business_name}", html)
