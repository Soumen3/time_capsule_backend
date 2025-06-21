from django.core.mail import send_mail
from django.conf import settings
import logging # Import logging
from django.utils.html import escape # For escaping text to be safely included in HTML
from django.utils.safestring import mark_safe # To mark a string as safe for HTML output

logger = logging.getLogger(__name__) # Get a logger instance
# Assuming settings.DISABLE_LOGGING is False for logging to be active
if hasattr(settings, 'DISABLE_LOGGING'):
    logger.disabled = settings.DISABLE_LOGGING

def send_capsule_link_email(recipient_email, capsule_title, capsule_id, owner_name, access_token, text_content=None):
    """
    Sends an email to the recipient with a unique link to view the capsule.
    Optionally includes text_content in the email body, styled with HTML.
    Returns: (bool, str_or_None) -> (success_status, message_or_error_string)
    """
    frontend_base_url = getattr(settings, 'FRONTEND_BASE_URL', 'http://localhost:5173')
    # Use the access_token for the public viewing link
    capsule_link = f"{frontend_base_url}/view-capsule/{access_token}/"

    subject = f"A Time Capsule from {owner_name} is ready for you!"
    
    # --- Plain text version (essential fallback) ---
    plain_message_intro = f"Hello,\n\nA time capsule titled \"{capsule_title}\" created by {owner_name} has been unsealed and is now available for you to view.\n"
    plain_text_content_section = ""
    if text_content:
        plain_text_content_section = f"\nHere's a message from the capsule:\n---\n{text_content}\n---\n"
    
    plain_message_link_and_outro = f"\nYou can view the full capsule contents, including any media, here:\n{capsule_link}\n\nEnjoy your journey to the past!\n\nSincerely,\nThe Time Capsule Team"
    plain_message_body = plain_message_intro + plain_text_content_section + plain_message_link_and_outro

    # --- HTML version ---
    # Basic styling for broad compatibility.
    # Using inline styles is generally recommended for HTML emails.
    html_body_style = "font-family: Arial, Helvetica, sans-serif; font-size: 14px; line-height: 1.6; color: #333;"
    html_link_style = "color: #007bff; text-decoration: none;"
    html_content_box_style = "margin-top: 20px; margin-bottom: 20px; padding: 15px; border: 1px solid #dddddd; background-color: #f9f9f9; border-radius: 4px;"

    html_message_intro = f"""
    <p>Hello,</p>
    <p>A time capsule titled "<strong>{escape(capsule_title)}</strong>" created by <em>{escape(owner_name)}</em> has been unsealed and is now available for you to view.</p>
    """

    html_text_content_section = ""
    if text_content:
        # Escape user content and replace newlines with <br> for HTML display.
        # The `white-space: pre-wrap;` style helps preserve whitespace and line breaks from the original text.
        formatted_text_content = escape(text_content) #.replace('\n', '<br />\n') # Using pre-wrap handles newlines
        html_text_content_section = f"""
    <div style="{html_content_box_style}">
        <p style="margin-top: 0; margin-bottom: 10px;"><strong>Here's a message from the capsule:</strong></p>
        <div style="white-space: pre-wrap; word-wrap: break-word;">{mark_safe(formatted_text_content)}</div>
    </div>
    """
    
    html_message_link_and_outro = f"""
    <p>You can view the full capsule contents, including any media, by clicking the link below:</p>
    <p><a href="{escape(capsule_link)}" style="{html_link_style}">View Your Time Capsule</a></p>
    <p>Enjoy your journey to the past!</p>
    <br />
    <p>Sincerely,<br />The Time Capsule Team</p>
    """

    # Assembling the full HTML body
    html_message_body = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{escape(subject)}</title>
    </head>
    <body style="{html_body_style}">
        {html_message_intro}
        {html_text_content_section}
        {html_message_link_and_outro}
    </body>
    </html>
    """

    from_email = settings.EMAIL_HOST_USER

    try:
        send_mail(
            subject,
            plain_message_body, # Plain text version
            from_email,
            [recipient_email],
            fail_silently=False,
            html_message=html_message_body # HTML version
        )
        logger.info(f"Capsule link email successfully sent to {recipient_email} for capsule ID {capsule_id}")
        return True, "Email sent successfully."
    except Exception as e:
        error_message = f"Error sending email for capsule ID {capsule_id} to {recipient_email} from {from_email}: {e}"
        logger.error(error_message)
        return False, error_message

