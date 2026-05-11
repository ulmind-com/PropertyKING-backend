"""
PropertyKING — Email Service
Email sending via Resend.
"""

import httpx
from app.config import settings

async def send_email(to: str, subject: str, html: str) -> bool:
    """Send an email via Brevo REST API."""
    if not settings.EMAIL_API_KEY:
        print("[WARN] EMAIL_API_KEY not set - skipping email")
        return False
        
    try:
        async with httpx.AsyncClient() as client:
            payload = {
                "sender": {"name": "PropertyKING", "email": settings.FROM_EMAIL},
                "to": [{"email": to}],
                "subject": subject,
                "htmlContent": html
            }
            headers = {
                "accept": "application/json",
                "api-key": settings.EMAIL_API_KEY,
                "content-type": "application/json"
            }
            
            response = await client.post(
                "https://api.brevo.com/v3/smtp/email",
                json=payload,
                headers=headers
            )
            
            if response.status_code in [200, 201, 202]:
                print(f"[OK] Email sent to {to}")
                return True
            else:
                print(f"[WARN] Brevo email failed: {response.status_code} - {response.text}")
                return False
                
    except Exception as e:
        print(f"[WARN] Email send exception: {e}")
        return False


async def send_welcome_email(email: str, name: str) -> bool:
    """Send welcome email to new user."""
    html = f"""
    <div style="font-family: 'Inter', Arial, sans-serif; max-width: 600px; margin: 0 auto; background: #f8fafc;">
        <div style="background: linear-gradient(135deg, #2563EB, #1E40AF); padding: 40px 30px; text-align: center; border-radius: 12px 12px 0 0;">
            <h1 style="color: white; margin: 0; font-size: 28px;">🏠 PropertyKING</h1>
            <p style="color: #bfdbfe; margin-top: 8px;">Welcome to the Premium Property Platform</p>
        </div>
        <div style="padding: 30px; background: white;">
            <h2 style="color: #0f172a; margin-top: 0;">Hey {name}! 👋</h2>
            <p style="color: #475569; line-height: 1.6;">Welcome to PropertyKING — the smarter way to find, list, and manage properties across the United States.</p>
            <p style="color: #475569; line-height: 1.6;">Start exploring thousands of verified listings or list your own property today!</p>
            <a href="#" style="display: inline-block; background: #2563EB; color: white; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; margin-top: 16px;">Get Started</a>
        </div>
        <div style="padding: 20px 30px; text-align: center; color: #94a3b8; font-size: 13px;">
            <p>© 2026 PropertyKING. All rights reserved.</p>
        </div>
    </div>
    """
    return await send_email(email, "Welcome to PropertyKING! 🏠", html)


async def send_password_reset_email(email: str, name: str, reset_token: str) -> bool:
    """Send password reset email."""
    reset_link = f"https://propertyking.com/reset-password?token={reset_token}"
    html = f"""
    <div style="font-family: 'Inter', Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #2563EB, #1E40AF); padding: 30px; text-align: center; border-radius: 12px 12px 0 0;">
            <h1 style="color: white; margin: 0;">🏠 PropertyKING</h1>
        </div>
        <div style="padding: 30px; background: white;">
            <h2 style="color: #0f172a; margin-top: 0;">Password Reset</h2>
            <p style="color: #475569;">Hi {name}, you requested a password reset. Click the button below to set a new password:</p>
            <a href="{reset_link}" style="display: inline-block; background: #2563EB; color: white; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; margin-top: 16px;">Reset Password</a>
            <p style="color: #94a3b8; font-size: 13px; margin-top: 20px;">This link expires in 1 hour. If you didn't request this, please ignore this email.</p>
        </div>
    </div>
    """
    return await send_email(email, "Reset Your Password — PropertyKING", html)


async def send_property_approved_email(email: str, name: str, property_title: str) -> bool:
    """Send email when property listing is approved."""
    html = f"""
    <div style="font-family: 'Inter', Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #10B981, #059669); padding: 30px; text-align: center; border-radius: 12px 12px 0 0;">
            <h1 style="color: white; margin: 0;">✅ Listing Approved!</h1>
        </div>
        <div style="padding: 30px; background: white;">
            <h2 style="color: #0f172a; margin-top: 0;">Great news, {name}!</h2>
            <p style="color: #475569;">Your property listing <strong>"{property_title}"</strong> has been reviewed and approved. It's now live and visible to all users!</p>
            <a href="#" style="display: inline-block; background: #10B981; color: white; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; margin-top: 16px;">View Listing</a>
        </div>
    </div>
    """
    return await send_email(email, f"Property Approved: {property_title} ✅", html)


async def send_property_rejected_email(email: str, name: str, property_title: str, reason: str) -> bool:
    """Send email when property listing is rejected."""
    html = f"""
    <div style="font-family: 'Inter', Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #EF4444, #DC2626); padding: 30px; text-align: center; border-radius: 12px 12px 0 0;">
            <h1 style="color: white; margin: 0;">❌ Listing Needs Changes</h1>
        </div>
        <div style="padding: 30px; background: white;">
            <h2 style="color: #0f172a; margin-top: 0;">Hi {name},</h2>
            <p style="color: #475569;">Your property listing <strong>"{property_title}"</strong> was not approved.</p>
            <div style="background: #fef2f2; border-left: 4px solid #ef4444; padding: 16px; margin: 16px 0; border-radius: 4px;">
                <strong style="color: #991b1b;">Reason:</strong>
                <p style="color: #7f1d1d; margin: 8px 0 0;">{reason}</p>
            </div>
            <p style="color: #475569;">Please update your listing and resubmit for review.</p>
        </div>
    </div>
    """
    return await send_email(email, f"Property Listing Update Required: {property_title}", html)


async def send_new_inquiry_email(email: str, name: str, property_title: str, inquirer_name: str, message: str) -> bool:
    """Send email when someone inquires about a property."""
    html = f"""
    <div style="font-family: 'Inter', Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #2563EB, #1E40AF); padding: 30px; text-align: center; border-radius: 12px 12px 0 0;">
            <h1 style="color: white; margin: 0;">💬 New Inquiry</h1>
        </div>
        <div style="padding: 30px; background: white;">
            <h2 style="color: #0f172a; margin-top: 0;">Hi {name},</h2>
            <p style="color: #475569;"><strong>{inquirer_name}</strong> is interested in your property <strong>"{property_title}"</strong>:</p>
            <div style="background: #f0f9ff; border-left: 4px solid #2563eb; padding: 16px; margin: 16px 0; border-radius: 4px;">
                <p style="color: #1e3a5f; margin: 0;">{message}</p>
            </div>
            <a href="#" style="display: inline-block; background: #2563EB; color: white; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; margin-top: 16px;">Respond Now</a>
        </div>
    </div>
    """
    return await send_email(email, f"New Inquiry: {property_title}", html)
