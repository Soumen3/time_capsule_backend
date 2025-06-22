from rest_framework import serializers
from .models import Capsule, CapsuleContent, CapsuleRecipient, CapsuleContentType, CapsuleRecipientStatus, Notification
from django.utils import timezone
from .tasks import deliver_capsule_email_task
import datetime
import logging

logger = logging.getLogger(__name__)

class CapsuleRecipientSerializer(serializers.ModelSerializer):
    class Meta:
        model = CapsuleRecipient
        fields = ['recipient_email', 'received_status'] # Add other fields if needed for response

class CapsuleContentSerializer(serializers.ModelSerializer):
    file_url = serializers.ReadOnlyField()
    class Meta:
        model = CapsuleContent
        fields = ['id', 'content_type', 'text_content', 'file', 'upload_date', 'order', "file_url"]

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        # representation.pop("file")  # <-- Remove this line to include 'file' in response
        return representation


class CapsuleSerializer(serializers.ModelSerializer):
    # Fields from the frontend that are not directly on the Capsule model
    # but are used to create related objects.
    # We use write_only=True as these fields are for input only during creation.
    text_content = serializers.CharField(write_only=True, required=False, allow_blank=True)
    media_files = serializers.ListField(
        child=serializers.FileField(), write_only=True, required=False
    )
    
    recipient_email = serializers.EmailField(write_only=True, required=True) # Assuming one recipient for now

    # To include related objects in the response (read-only)
    contents = CapsuleContentSerializer(many=True, read_only=True)
    recipients = CapsuleRecipientSerializer(many=True, read_only=True) # For showing recipient in response

    class Meta:
        model = Capsule
        fields = [
            'id', 'owner', 'title', 'description',
            'delivery_date', 'delivery_time',
            'creation_date', 'is_delivered', 'is_archived',
            'delivery_method', 'privacy_status',
            # Write-only fields for creation
            'text_content', 'media_files', 'recipient_email',
            # Read-only fields for response
            'contents', 'recipients'
        ]
        read_only_fields = ['owner', 'id', 'creation_date', 'is_delivered', 'is_archived']

    def get_file_content_type(self, file):
        # Basic content type detection based on file extension
        # You might want a more robust solution (e.g., using python-magic)
        name = file.name.lower()
        if name.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff')):
            return CapsuleContentType.IMAGE
        elif name.endswith(('.mp4', '.avi', '.mov', '.webm', '.mkv', '.flv', '.wmv')):
            return CapsuleContentType.VIDEO
        elif name.endswith(('.mp3', '.wav', '.ogg', '.m4a', '.flac', '.aac', '.wma')):
            return CapsuleContentType.AUDIO
        elif name.endswith(('.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt', '.epub')):
            return CapsuleContentType.DOCUMENT
        return CapsuleContentType.DOCUMENT # Default or raise error

    def create(self, validated_data):
        owner = self.context['request'].user
        
        media_files_data = validated_data.pop('media_files', [])
        text_content_data = validated_data.pop('text_content', None)
        recipient_email_data = validated_data.pop('recipient_email')

        delivery_date = validated_data.get('delivery_date')
        delivery_time = validated_data.get('delivery_time')
        
        eta_datetime_utc = None
        if delivery_date and delivery_time:
            try:
                # Create a naive datetime object from date and time
                naive_datetime = datetime.datetime.combine(delivery_date, delivery_time)
                logger.debug(f"Naive datetime created: {naive_datetime}")

                # Make it timezone-aware using Django's default timezone
                aware_datetime_local = timezone.make_aware(naive_datetime, timezone.get_default_timezone())
                logger.debug(f"Aware datetime (local TZ): {aware_datetime_local}")

                # Convert this local aware datetime to UTC for Celery ETA
                eta_datetime_utc = aware_datetime_local.astimezone(datetime.timezone.utc)
                logger.info(f"Calculated ETA (UTC) for capsule: {eta_datetime_utc}")

            except Exception as e:
                logger.error(f"Error creating delivery datetime: {e}")
                # Decide how to handle this - perhaps don't schedule or raise error

        # Create the capsule instance
        capsule = Capsule.objects.create(owner=owner, **validated_data)

        # Create CapsuleContent for the text message if provided
        if text_content_data:
            CapsuleContent.objects.create(
                capsule=capsule,
                content_type=CapsuleContentType.TEXT,
                text_content=text_content_data,
                order=0 # Assuming text content is first
            )

        # Create CapsuleContent for each uploaded media file
        file_order_start = 1 if text_content_data else 0
        for index, file_data in enumerate(media_files_data):
            content_type = self.get_file_content_type(file_data)
            CapsuleContent.objects.create(
                capsule=capsule,
                content_type=content_type,
                file=file_data,
                order=file_order_start + index
            )
        
        recipient_obj = CapsuleRecipient.objects.create(
            capsule=capsule,
            recipient_email=recipient_email_data
        )

        # Schedule the Celery task for email delivery
        current_time_utc = timezone.now().astimezone(datetime.timezone.utc)
        
        if eta_datetime_utc:
            if eta_datetime_utc > current_time_utc:
                deliver_capsule_email_task.apply_async(
                    args=[capsule.id, recipient_obj.id],
                    eta=eta_datetime_utc
                )
                logger.info(f"Capsule ID {capsule.id} delivery scheduled for {eta_datetime_utc} (UTC) to {recipient_obj.recipient_email}")
            else: # ETA is in the past or now
                deliver_capsule_email_task.apply_async(
                    args=[capsule.id, recipient_obj.id],
                    countdown=10 # Execute in 10 seconds for past/current ETAs
                )
                logger.info(f"Capsule ID {capsule.id} delivery ETA {eta_datetime_utc} (UTC) is past/now. Scheduled for near-immediate delivery to {recipient_obj.recipient_email}")
        else:
            logger.warning(f"Capsule ID {capsule.id} has no valid delivery date/time for scheduling email.")

        return capsule

# --- Serializers for Public Capsule View ---

class PublicCapsuleContentSerializer(serializers.ModelSerializer):
    file_url = serializers.ReadOnlyField()
    class Meta:
        model = CapsuleContent
        fields = ['id', 'content_type', 'text_content', 'file', 'order', 'file_url'] # Exclude upload_date for public?
        read_only_fields = fields
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        # representation.pop("file")  # <-- Remove this line to include 'file' in response
        return representation

class PublicCapsuleOwnerSerializer(serializers.Serializer): # Simple serializer for owner's name
    name = serializers.CharField()
    # Add other public-safe owner fields if needed, e.g., a public profile URL

class PublicCapsuleSerializer(serializers.ModelSerializer):
    contents = PublicCapsuleContentSerializer(many=True, read_only=True)
    # Instead of full owner object, provide a simplified owner representation
    # This assumes your User model has a 'name' attribute. Adjust if different.
    owner_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Capsule
        fields = [
            'id', 'title', 'description', 
            'delivery_date', # To show when it was unsealed
            'owner_name', # Simplified owner info
            'contents'
        ]
        read_only_fields = fields

    def get_owner_name(self, obj):
        owner = obj.owner
        if hasattr(owner, 'name') and owner.name:
            return owner.name
        elif hasattr(owner, 'email') and owner.email: # Fallback, consider privacy implications
            return owner.email.split('@')[0] # Example: show only username part
        return "The Sender"

class NotificationSerializer(serializers.ModelSerializer):
    capsule_title = serializers.CharField(source='capsule.title', read_only=True, allow_null=True)
    created_at_formatted = serializers.DateTimeField(source='created_at', format="%b %d, %Y %I:%M %p", read_only=True)

    class Meta:
        model = Notification
        fields = [
            'id', 
            'message', 
            'notification_type', 
            'is_read', 
            'created_at',
            'created_at_formatted',
            'read_at', 
            'capsule', # Send capsule ID
            'capsule_title'
        ]
        read_only_fields = ['id', 'created_at', 'read_at', 'capsule_title']
        read_only_fields = ['id', 'created_at', 'read_at', 'capsule_title']
