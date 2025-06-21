from celery import shared_task
from django.utils import timezone
from django.conf import settings
from .models import (
    Capsule, 
    CapsuleContent, 
    CapsuleRecipient, 
    CapsuleRecipientStatus, 
    DeliveryLog, 
    CapsuleDeliveryMethod, 
    DeliveryLogStatus, 
    CapsuleContentType, 
    CapsuleContentType,
    Notification,
    NotificationType
)
from .utils import send_capsule_link_email
import datetime
import logging
import uuid # Import uuid

logger = logging.getLogger(__name__)
logger.disabled = settings.DISABLE_LOGGING  # Use the global setting to control logging

@shared_task(
    bind=True, 
    name='capsules.deliver_capsule_email', # Explicit task name
    max_retries=3, 
    default_retry_delay=2 * 60
)
def deliver_capsule_email_task(self, capsule_id, recipient_id):
    """
    Celery task to deliver a capsule email to a specific recipient.
    """
    try:
        logger.info(f"Starting delivery task for capsule ID {capsule_id} to recipient ID {recipient_id}")
        capsule = Capsule.objects.get(pk=capsule_id)
        recipient = CapsuleRecipient.objects.get(pk=recipient_id, capsule=capsule)

        if capsule.is_delivered and recipient.received_status == CapsuleRecipientStatus.SENT:
            logger.info(f"Capsule ID {capsule_id} already delivered to recipient {recipient.recipient_email}. Skipping.")
            return f"Capsule {capsule_id} already delivered to {recipient.recipient_email}."

        logger.info(f"Attempting to deliver capsule ID {capsule_id} to {recipient.recipient_email}")

        # Construct owner's name - assuming owner has a 'name' attribute
        owner = capsule.owner
        owner_name = "A friend" # Default fallback
        if hasattr(owner, 'name') and owner.name:
            owner_name = owner.name
        elif hasattr(owner, 'email') and owner.email: # Fallback to email if name is not set
             owner_name = owner.email

        # Ensure recipient has an access token
        if not recipient.access_token:
            recipient.access_token = uuid.uuid4()
            recipient.token_generated_at = timezone.now()
            recipient.save(update_fields=['access_token', 'token_generated_at'])
            logger.info(f"Generated access token for recipient ID {recipient.id}")


        # Fetch first text content if available
        
        first_text_content_obj = CapsuleContent.objects.filter(
            capsule=capsule, 
            content_type=CapsuleContentType.TEXT
        ).first()  # Get the first text content object
        # If no text content, set to None
        text_content_for_email = first_text_content_obj.text_content if first_text_content_obj else None
        logger.info(f"Text content for email: {text_content_for_email}")

        # send_capsule_link_email now returns a tuple: (bool_success, message_string)
        email_sent_successfully, email_status_message = send_capsule_link_email(
            recipient_email=recipient.recipient_email,
            capsule_title=capsule.title,
            capsule_id=capsule.id, # Still useful for internal reference
            owner_name=owner_name,
            text_content=text_content_for_email,
            access_token=recipient.access_token # Pass the access token
        )

        if email_sent_successfully: # Check the boolean success flag
            capsule.is_delivered = True # Mark main capsule as delivered
            capsule.is_unlocked = True  # Mark capsule as unlocked since the link is sent
            capsule.save(update_fields=['is_delivered', 'is_unlocked'])

            recipient.received_status = CapsuleRecipientStatus.SENT
            recipient.sent_date = timezone.now()
            recipient.save(update_fields=['received_status', 'sent_date'])

            DeliveryLog.objects.create(
                capsule=capsule,
                delivery_method=CapsuleDeliveryMethod.EMAIL, 
                recipient_email=recipient.recipient_email,
                status=DeliveryLogStatus.SUCCESS,
                details=email_status_message # Store success message
            )
            logger.info(f"Successfully delivered capsule ID {capsule_id} to {recipient.recipient_email}: {email_status_message}")

            # Create "Capsule Delivered" notification for the owner
            try:
                Notification.objects.create(
                    user=capsule.owner,
                    capsule=capsule,
                    message=f"Your time capsule '{capsule.title}' has been successfully delivered to {recipient.recipient_email}.",
                    notification_type=NotificationType.DELIVERY_SUCCESS
                )
                logger.info(f"Delivery notification created for capsule ID {capsule.id} to {recipient.recipient_email}")
            except Exception as e:
                logger.error(f"Failed to create delivery notification for capsule ID {capsule.id}: {e}")
            
            return f"Successfully delivered capsule {capsule_id} to {recipient.recipient_email}."
        else:
            # Email sending failed
            recipient.received_status = CapsuleRecipientStatus.FAILED
            recipient.save(update_fields=['received_status'])
            # Create "Capsule Delivery Failed" notification for the owner
            try:
                Notification.objects.create(
                    user=capsule.owner,
                    capsule=capsule,
                    message=f"Failed to deliver your time capsule '{capsule.title}' to {recipient.recipient_email}. Reason: {email_status_message}",
                    notification_type=NotificationType.DELIVERY_FAIL
                )
            except Exception as e:
                logger.error(f"Failed to create delivery failure notification for capsule ID {capsule.id}: {e}")

            DeliveryLog.objects.create(
                capsule=capsule,
                delivery_method=CapsuleDeliveryMethod.EMAIL,
                recipient_email=recipient.recipient_email,
                status=DeliveryLogStatus.FAILURE,
                error_message="Email sending failed via Celery task.", # Generic error
                details=email_status_message # Store specific error from send_capsule_link_email
            )
            logger.error(f"Email sending failed for capsule ID {capsule_id} to {recipient.recipient_email}. Specific error: {email_status_message}")
            # Raise an exception with the specific error message to trigger Celery retry
            raise Exception(f"Email sending failed: {email_status_message}")

    except Capsule.DoesNotExist:
        logger.exception(f"Capsule ID {capsule_id} not found. Cannot deliver.")
        # Do not retry if capsule doesn't exist
        return f"Capsule {capsule_id} not found."
    except CapsuleRecipient.DoesNotExist:
        logger.exception(f"Recipient ID {recipient_id} for Capsule ID {capsule_id} not found. Cannot deliver.")
        # Do not retry if recipient doesn't exist
        return f"Recipient {recipient_id} for capsule {capsule_id} not found."
    except Exception as exc:
        logger.exception(f"An error occurred delivering capsule ID {capsule_id} to recipient ID {recipient_id}: {exc}")
        # Retry the task for other exceptions (like network issues during email sending)
        raise self.retry(exc=exc)

