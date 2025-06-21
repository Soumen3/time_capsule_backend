from django.core.mail import EmailMessage
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class Util:
    @staticmethod
    def send_email(data):
        try:
            email = EmailMessage(
                subject=data['email_subject'],
                body=data['email_body'],
                from_email=settings.EMAIL_HOST_USER,
                to=[data['to_email']]
            )
            email.send()
            logger.info(f"Email sent successfully to {data['to_email']} with subject '{data['email_subject']}'")
            return True
        except Exception as e:
            logger.error(f"Error sending email to {data['to_email']} for subject '{data['email_subject']}': {e}")
            return False