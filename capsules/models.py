# capsules/models.py
from django.db import models
from django.conf import settings # To refer to the custom User model
from django.utils import timezone
from django.core.validators import FileExtensionValidator # Import for file validation
import datetime # Import datetime
import uuid # Import UUID for access tokens
import os # Import os for path joining
import logging # Import the logging library
from cloudinary.models import CloudinaryField


logger = logging.getLogger(__name__) # Get a logger instance for this module

# --- Choices for CharFields to ensure data consistency ---
class CapsuleDeliveryMethod(models.TextChoices):
    EMAIL = 'email', 'Email'
    IN_APP = 'in_app', 'In-App Notification'
    SMS = 'sms', 'SMS' # Potentially add later if needed

class CapsulePrivacyStatus(models.TextChoices):
    PRIVATE = 'private', 'Private (Only owner can access)'
    SHARED = 'shared', 'Shared (Specific recipients can access)'
    # PUBLIC = 'public', 'Public (Viewable by anyone, potentially)' # Consider carefully


class CapsuleContentType(models.TextChoices):
    TEXT = 'text', 'Text'
    IMAGE = 'image', 'Image'
    VIDEO = 'video', 'Video'
    AUDIO = 'audio', 'Audio'
    DOCUMENT = 'document', 'Document'


class CapsuleRecipientStatus(models.TextChoices):
    PENDING = 'pending', 'Pending Delivery'
    SENT = 'sent', 'Sent'
    FAILED = 'failed', 'Failed'
    OPENED = 'opened', 'Opened' # If you implement tracking

class DeliveryLogStatus(models.TextChoices):
    SUCCESS = 'success', 'Success'
    FAILURE = 'failure', 'Failure'
    PENDING = 'pending', 'Pending (e.g., for async email service)'

class NotificationType(models.TextChoices):
    CAPSULE_CREATED= 'capsule_created', 'Capsule Created'
    DELIVERY_SUCCESS = 'delivery_success', 'Capsule Delivered'
    DELIVERY_FAIL = 'delivery_fail', 'Capsule Delivery Failed'
    NEW_SHARED_CAPSULE = 'new_shared_capsule', 'New Shared Capsule'
    CAPSULE_OPENED = 'capsule_opened', 'Capsule Opened' # New type
    REMINDER = 'reminder', 'Reminder'
    SYSTEM_ALERT = 'system_alert', 'System Alert'
    TRANSFER_NOTIFICATION = 'transfer_notification', 'Capsule Transferred'


# --- Core Capsule Model ---
class Capsule(models.Model):
    """
    Represents the main time capsule, holding its metadata and delivery schedule.
    """
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='owned_capsules',
        help_text="The user who created and owns this capsule."
    )
    title = models.CharField(max_length=255, help_text="A descriptive title for the capsule.")
    description = models.TextField(
        blank=True,
        help_text="Optional longer description for the capsule's purpose or contents."
    )
    creation_date = models.DateTimeField(
        default=timezone.now,
        help_text="The exact date and time the capsule was created."
    )
    # delivery_date stores both date and time
    delivery_date = models.DateField(
        help_text="The scheduled date and time for the capsule to be delivered."
    )
    delivery_time = models.TimeField(
        default=datetime.time(hour=0, minute=0),  # 12:00 AM midnight
        help_text="The scheduled time for the capsule to be delivered on the delivery_date."
    )
    is_delivered = models.BooleanField(
        default=False,
        help_text="Indicates if the capsule has been delivered."
    )
    is_archived = models.BooleanField(
        default=False,
        help_text="Indicates if the capsule is archived by the owner (e.g., after delivery)."
    )
    is_unlocked = models.BooleanField(
        default=False,
        help_text="Indicates if the capsule has been unlocked by the owner or recipient."
    )
    delivery_method = models.CharField(
        max_length=50,
        choices=CapsuleDeliveryMethod.choices,
        default=CapsuleDeliveryMethod.EMAIL,
        help_text="The primary method for delivering the capsule content."
    )
    privacy_status = models.CharField(
        max_length=50,
        choices=CapsulePrivacyStatus.choices,
        default=CapsulePrivacyStatus.PRIVATE,
        help_text="Determines who can access the capsule's contents."
    )
    # Fields for 'legacy management' / account inactivity
    transfer_on_inactivity = models.BooleanField(
        default=False,
        help_text="If true, capsule content may be transferred if owner account becomes inactive."
    )
    transfer_recipient_email = models.EmailField(
        blank=True, null=True,
        help_text="Email of the designated recipient for transfer on inactivity."
    )

    class Meta:
        verbose_name = "Time Capsule"
        verbose_name_plural = "Time Capsules"
        ordering = ['delivery_date'] # Default ordering for querying

    def __str__(self):
        return f"Capsule '{self.title}' by {self.owner.email} (ID: {self.id})"

    # Custom methods to check if capsule is due
    def is_due_for_delivery(self):
        return not self.is_delivered and self.delivery_date <= timezone.now()


# --- Capsule Content Model (Handles Text, Images, Videos, Documents, Audio) ---
def user_capsule_content_path(instance, filename):
    """
    Generates a unique path for uploaded capsule content files.
    Path: capsule_files/<user_email_sanitized>/capsule_<capsule_id>/<filename>
    
    Note: Using user email directly in paths can be problematic if emails contain
    special characters not suitable for all filesystems or S3 key names.
    Consider sanitizing the email or using user_id instead for robustness.
    For S3, most characters are fine, but it's a good practice to be mindful.
    """
    # Sanitize email to be filesystem/URL friendly
    user_email_path_segment = instance.capsule.owner.email.replace('@', '_at_').replace('.', '_dot_')
    # Further sanitize by removing characters not typically allowed in directory names
    # This is a basic example; a more robust slugify function might be better.
    user_email_path_segment = "".join(c if c.isalnum() or c in ['_', '-'] else '_' for c in user_email_path_segment)
    
    capsule_id_path_segment = f"capsule_{instance.capsule.id}"
    
    # Path will be capsule_files/sanitized_email/capsule_id/filename
    return os.path.join('capsule_files', user_email_path_segment, capsule_id_path_segment, filename)

class CapsuleContent(models.Model):
    """
    Stores individual content items for a time capsule.
    Uses a single table for all content types, with fields being null where not applicable.
    """
    capsule = models.ForeignKey(
        'Capsule', # Use string reference if Capsule is defined later or in another app
        on_delete=models.CASCADE, # <--- This is important
        related_name='contents',
        help_text="The capsule this content belongs to."
    )
    content_type = models.CharField(
        max_length=50,
        choices=CapsuleContentType.choices,
        help_text="The type of content stored (text, image, video, audio, document)."
    )
    text_content = models.TextField(
        blank=True, null=True,
        help_text="Text content for 'text' type capsules. Null for file-based content."
    )
    file = CloudinaryField(
        'file',  # This is the verbose name, often used as a default public_id prefix if not specified
        blank=True,
        null=True,
        resource_type='auto', # Cloudinary will auto-detect based on file type
        validators=[
            FileExtensionValidator(
                allowed_extensions=[
                    'jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'tiff', # Images
                    'mp4', 'avi', 'mov', 'webm', 'mkv', 'flv', 'wmv', # Videos
                    'mp3', 'wav', 'ogg', 'm4a', 'flac', 'aac', 'wma', # Audio
                    'pdf', 'doc', 'docx', 'txt', 'rtf', 'odt', 'epub' # Documents
                ]
            )
        ],
        help_text="File content for 'image', 'video', 'audio', 'document' types. Null for text content."
    )
    upload_date = models.DateTimeField(
        auto_now_add=True,
        help_text="Date and time when this content was uploaded."
    )
    order = models.PositiveIntegerField(
        default=0,
        help_text="Order of content within a capsule (for display purposes)."
    )

    def delete(self, *args, **kwargs):
        file_path = None
        if self.file:
            file_path = self.file.name
            logger.info(f"Attempting to delete file from storage: {file_path} for CapsuleContent ID: {self.id}")
            try:
                self.file.delete(save=False)
                logger.info(f"Successfully deleted file from storage: {file_path}")
            except Exception as e:
                logger.error(f"Error deleting file {file_path} from storage: {e}", exc_info=True)
                # Decide if you want to proceed with DB deletion even if file deletion fails.
                # For now, we'll log the error and continue to delete the DB record.
        
        super().delete(*args, **kwargs) # Call the "real" delete() method
        logger.info(f"Successfully deleted CapsuleContent record ID: {self.id} from database (associated file: {file_path or 'N/A'}).")

    class Meta:
        verbose_name = "Capsule Content"
        verbose_name_plural = "Capsule Contents"
        ordering = ['order']
        # Add a constraint to ensure either text_content or file is present
        constraints = [
            models.CheckConstraint(
                check=models.Q(text_content__isnull=False) | models.Q(file__isnull=False),
                name='text_or_file_content_required'
            )
        ]

    def __str__(self):
        return f"Content for Capsule '{self.capsule.title}' ({self.content_type})"
    
    @property
    def file_url(self):
        if self.file:
            return self.file.url
        return None



# --- Capsule Recipient Model ---
class CapsuleRecipient(models.Model):
    """
    Defines who will receive a time capsule.
    A capsule can have multiple recipients.
    """
    capsule = models.ForeignKey(
        Capsule,
        on_delete=models.CASCADE,
        related_name='recipients',
        help_text="The capsule this recipient is associated with."
    )
    recipient_email = models.EmailField(
        help_text="The email address of the person who will receive the capsule."
    )
    recipient_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='received_capsules',
        blank=True, null=True,
        help_text="Optional: If the recipient is also a registered user."
    )
    received_status = models.CharField(
        max_length=20,
        choices=CapsuleRecipientStatus.choices,
        default=CapsuleRecipientStatus.PENDING,
        help_text="Status of the capsule delivery to this specific recipient."
    )
    sent_date = models.DateTimeField(
        blank=True, null=True,
        help_text="The date and time the capsule was sent to this recipient."
    )
    access_token = models.UUIDField(
        default=uuid.uuid4, # Generates a default UUID
        editable=False, 
        unique=True, 
        null=True, # Allow null initially for existing records, can be False after migration
        blank=True, # Allow blank initially
        help_text="Unique token for unauthenticated access to this recipient's view of the capsule."
    )
    token_generated_at = models.DateTimeField(
        auto_now_add=True, # Automatically set when the token is generated
        null=True, blank=True,
        help_text="Timestamp when the access token was generated or last refreshed."
    )


    class Meta:
        verbose_name = "Capsule Recipient"
        verbose_name_plural = "Capsule Recipients"
        unique_together = ('capsule', 'recipient_email') # A recipient email can only be added once per capsule

    def __str__(self):
        return f"Recipient {self.recipient_email} for Capsule '{self.capsule.title}'"


# --- Delivery Log Model ---
class DeliveryLog(models.Model):
    """
    Logs the delivery attempts and status of time capsules.
    """
    capsule = models.ForeignKey(
        Capsule,
        on_delete=models.CASCADE,
        related_name='delivery_logs',
        help_text="The capsule that was attempted to be delivered."
    )
    delivery_attempt_time = models.DateTimeField(
        auto_now_add=True,
        help_text="The date and time of this delivery attempt."
    )
    delivery_method = models.CharField(
        max_length=50,
        choices=CapsuleDeliveryMethod.choices, # Reusing choices from Capsule model
        help_text="The method used for this specific delivery attempt."
    )
    recipient_email = models.EmailField(
        blank=True, null=True,
        help_text="The email of the recipient (if applicable to the method)."
    )
    recipient_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True, null=True,
        help_text="The user ID of the recipient (if applicable to the method)."
    )
    status = models.CharField(
        max_length=50,
        choices=DeliveryLogStatus.choices,
        default=DeliveryLogStatus.PENDING,
        help_text="The outcome of the delivery attempt."
    )
    error_message = models.TextField(
        blank=True, null=True,
        help_text="Detailed error message if the delivery failed."
    )
    details = models.TextField(
        blank=True, null=True,
        help_text="Additional details about the delivery attempt, such as success messages or logs."
    )

    class Meta:
        verbose_name = "Delivery Log"
        verbose_name_plural = "Delivery Logs"
        ordering = ['-delivery_attempt_time']

    def __str__(self):
        recipient_info = self.recipient_email or (self.recipient_user.email if self.recipient_user else 'Unknown')
        return (
            f"Delivery Log for Capsule '{self.capsule.title}' "
            f"to {recipient_info} - {self.status}"
        )


# --- Notification Model ---
class Notification(models.Model):
    """
    Stores in-app notifications for users.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        help_text="The user who receives this notification."
    )
    capsule = models.ForeignKey(
        Capsule,
        on_delete=models.SET_NULL,
        blank=True, null=True,
        related_name='notifications',
        help_text="The capsule related to this notification (optional)."
    )
    message = models.TextField(
        help_text="The content of the notification."
    )
    notification_type = models.CharField(
        max_length=50,
        choices=NotificationType.choices,
        help_text="Categorizes the type of notification."
    )
    is_read = models.BooleanField(
        default=False,
        help_text="Indicates if the user has viewed this notification."
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="The date and time the notification was created."
    )
    read_at = models.DateTimeField(
        blank=True, null=True,
        help_text="The date and time the notification was read."
    )

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.user.email}: {self.notification_type}"

