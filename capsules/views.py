from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, viewsets, generics
from rest_framework.permissions import IsAuthenticated, AllowAny
from .serializers import CapsuleSerializer, PublicCapsuleSerializer, NotificationSerializer, NotificationSerializer
from .models import (
    Capsule, 
    CapsuleContent, 
    CapsuleRecipient, 
    CapsuleRecipientStatus, 
    Notification, 
    NotificationType)
from django.utils import timezone
from django.http import Http404
from .renderer import CapsuleRenderer
from rest_framework.parsers import MultiPartParser, FormParser # For file uploads
import uuid
import datetime # Import datetime
from django.conf import settings # Import settings for DEBUG check
import logging
logger = logging.getLogger(__name__)

# Create your views here.
class CreateCapsuleView(APIView):
    permission_classes = [IsAuthenticated]
    renderer_classes = [CapsuleRenderer]
    parser_classes = [MultiPartParser, FormParser] # Add parsers for FormData
    """
    View to create a new capsule.
    """
    def post(self, request, *args, **kwargs):
        # Pass context to the serializer, which includes the request object.
        # This allows the serializer to access request.user.
        serializer = CapsuleSerializer(data=request.data, context={'request': request})
        
        if serializer.is_valid():
            # The owner is set within the serializer's create method using self.context['request'].user
            capsule = serializer.save() 

            # Create a notification for the owner
            try:
                Notification.objects.create(
                    user=capsule.owner,
                    capsule=capsule,
                    message=f"Your time capsule '{capsule.title}' has been successfully created and sealed.",
                    notification_type=NotificationType.CAPSULE_CREATED 
                )
                logger.info(f"Notification created for capsule ID {capsule.id} creation, user {capsule.owner.email}")
            except Exception as e:
                logger.error(f"Failed to create notification for capsule ID {capsule.id} creation: {e}")

            # Re-serialize the created capsule instance to include related objects for the response
            response_serializer = CapsuleSerializer(capsule, context={'request': request})
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        
        # Print errors for debugging if validation fails
        print("Serializer Errors:", serializer.errors) 
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class CapsuleListView(APIView):
    permission_classes = [IsAuthenticated]
    renderer_classes = [CapsuleRenderer]

    def get(self, request, *args, **kwargs):
        # Retrieve all capsules owned by the currently authenticated user
        # and that are not archived.
        capsules = Capsule.objects.filter(owner=request.user, is_archived=False).order_by('-creation_date')
        
        # If you want to paginate, you would integrate Django REST Framework's pagination here.
        # For now, returning all non-archived capsules.
        
        serializer = CapsuleSerializer(capsules, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

class CapsuleDetailView(APIView): # Example: A view to get details of a single capsule
    permission_classes = [IsAuthenticated]
    renderer_classes = [CapsuleRenderer]

    def get(self, request, pk, *args, **kwargs): # pk would be the capsule's ID
        try:
            capsule = Capsule.objects.get(pk=pk, owner=request.user) # Ensure owner can access
        except Capsule.DoesNotExist:
            return Response({"error": "Capsule not found or access denied."}, status=status.HTTP_404_NOT_FOUND)
        
        # The serializer will automatically include the 'contents'
        serializer = CapsuleSerializer(capsule, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

class CapsuleDeleteView(APIView):
    permission_classes = [IsAuthenticated]
    renderer_classes = [CapsuleRenderer] # Or default JSONRenderer if no custom rendering needed

    def delete(self, request, pk, *args, **kwargs):
        try:
            capsule = Capsule.objects.get(pk=pk, owner=request.user)
        except Capsule.DoesNotExist:
            return Response({"error": "Capsule not found or you do not have permission to delete it."}, status=status.HTTP_404_NOT_FOUND)
        
        capsule_title = capsule.title # For logging or response message
        owner = capsule.owner

        # --- Placeholder for Celery Task Revocation ---
        # To revoke a Celery task, you need its task_id.
        # Assuming you store task_id on the Capsule model, e.g., as 'delivery_task_id':
        # if capsule.delivery_task_id:
        #     try:
        #         from time_capsule_backend.celery import app as celery_app # Ensure Celery app is imported
        #         celery_app.control.revoke(capsule.delivery_task_id, terminate=True)
        #         logger.info(f"Revoked Celery task {capsule.delivery_task_id} for capsule ID {pk} being deleted.")
        #     except Exception as e:
        #         logger.error(f"Error revoking Celery task {capsule.delivery_task_id} for capsule ID {pk}: {e}")
        # else:
        #     logger.warning(f"No delivery_task_id found for capsule ID {pk}. Cannot revoke Celery task.")
        # --- End Placeholder ---

        # Perform the deletion
        capsule.delete()
        
        logger.info(f"Capsule '{capsule_title}' (ID: {pk}) deleted by user {request.user.email}.")

        # Create a notification for the owner about the deletion
        try:
            Notification.objects.create(
                user=owner,
                # capsule=None, # Capsule is deleted, so can't link directly. Or link before delete if needed.
                message=f"Your time capsule '{capsule_title}' and any scheduled deliveries have been successfully canceled and deleted.",
                notification_type=NotificationType.SYSTEM_ALERT # Or a more specific type like CAPSULE_DELETED
            )
            logger.info(f"Notification created for deletion of capsule '{capsule_title}' for user {owner.email}")
        except Exception as e:
            logger.error(f"Failed to create notification for deletion of capsule '{capsule_title}': {e}")

        return Response({"message": f"Capsule '{capsule_title}' successfully deleted."}, status=status.HTTP_204_NO_CONTENT)


class CapsuleViewSet(viewsets.ModelViewSet):
    # Assuming you will define this viewset for other capsule-related actions
    queryset = Capsule.objects.all()
    serializer_class = CapsuleSerializer
    permission_classes = [IsAuthenticated]
    renderer_classes = [CapsuleRenderer]

class PublicCapsuleRetrieveView(generics.RetrieveAPIView):
    """
    Allows unauthenticated access to view a specific capsule's details using a unique access token.
    """
    permission_classes = [AllowAny]
    serializer_class = PublicCapsuleSerializer
    queryset = Capsule.objects.all() # Base queryset, will be filtered in get_object

    def get_object(self):
        access_token_str = str(self.kwargs.get('access_token'))
        try:
            # Validate UUID format before querying
            access_token = uuid.UUID(access_token_str, version=4)
            logger.debug(f"Access token UUID validated: {access_token}")
        except ValueError:
            raise Http404("Invalid token format.")

        try:
            # Fetch the recipient by the access token
            # Ensure the capsule is selected to avoid extra DB hit
            recipient = CapsuleRecipient.objects.select_related('capsule', 'capsule__owner').get(access_token=access_token)
        except CapsuleRecipient.DoesNotExist:
            raise Http404("Capsule not found or access token is invalid.") # Corrected error message

        capsule = recipient.capsule

        # Check if the capsule is actually "unlocked" for viewing based on delivery date and time
        current_datetime = timezone.now()
        # Combine date and time from the capsule model, then make it timezone-aware
        delivery_datetime_naive = datetime.datetime.combine(capsule.delivery_date, capsule.delivery_time)
        delivery_datetime_aware = timezone.make_aware(delivery_datetime_naive, timezone.get_default_timezone())

        if delivery_datetime_aware > current_datetime and not settings.DEBUG:
            logger.warning(f"Attempt to access capsule ID {capsule.id} via token {access_token} before delivery time.")
            raise Http404("This time capsule is not yet available.")

        # Additionally, check if the capsule itself is marked as unlocked
        if not capsule.is_unlocked and not settings.DEBUG: # Allow viewing in DEBUG even if not explicitly unlocked
            logger.warning(f"Attempt to access capsule ID {capsule.id} (not unlocked) via token {access_token}.")
            raise Http404("This time capsule is not currently accessible.")


        # Log access and update recipient status to 'OPENED' if it was 'SENT'
        # This should ideally only happen once per recipient.
        if recipient.received_status == CapsuleRecipientStatus.SENT:
            recipient.received_status = CapsuleRecipientStatus.OPENED
            # You might want to record the opened_at time as well if you add such a field
            # recipient.opened_at = timezone.now() 
            recipient.save(update_fields=['received_status'])
            logger.info(f"Capsule ID {capsule.id} opened by recipient {recipient.recipient_email} via token {access_token}.")

            # Create a notification for the capsule owner
            try:
                Notification.objects.create(
                    user=capsule.owner,
                    capsule=capsule,
                    message=f"Your time capsule '{capsule.title}' was opened by {recipient.recipient_email}.",
                    notification_type=NotificationType.CAPSULE_OPENED
                )
                logger.info(f"Notification created for capsule ID {capsule.id} opened by {recipient.recipient_email}, for owner {capsule.owner.email}")
            except Exception as e:
                logger.error(f"Failed to create notification for capsule ID {capsule.id} opening: {e}")

        elif recipient.received_status == CapsuleRecipientStatus.PENDING and delivery_datetime_aware <= current_datetime:
            # If for some reason the status was PENDING but it's now due and accessed, mark as OPENED.
            # This might indicate an issue in the delivery task not updating status to SENT.
            recipient.received_status = CapsuleRecipientStatus.OPENED
            recipient.save(update_fields=['received_status'])
            logger.info(f"Capsule ID {capsule.id} (status PENDING) opened by recipient {recipient.recipient_email} via token {access_token}.")
            # Also create a notification for the owner in this case
            try:
                Notification.objects.create(
                    user=capsule.owner,
                    capsule=capsule,
                    message=f"Your time capsule '{capsule.title}' was opened by {recipient.recipient_email} (was pending).",
                    notification_type=NotificationType.CAPSULE_OPENED
                )
                logger.info(f"Notification created for capsule ID {capsule.id} opened (from pending) by {recipient.recipient_email}, for owner {capsule.owner.email}")
            except Exception as e:
                logger.error(f"Failed to create notification for capsule ID {capsule.id} opening (from pending): {e}")


        return capsule

# In your urls.py, you would have a path like:
# path('capsules/<int:pk>/', CapsuleDetailView.as_view(), name='capsule-detail'),
# path('public-capsule/<uuid:access_token>/', PublicCapsuleRetrieveView.as_view(), name='public-capsule-detail')


# --- Notification Views ---

class NotificationListView(generics.ListAPIView):
    """
    List all notifications for the authenticated user.
    Optionally filter by 'is_read' status.
    """
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    renderer_classes = [CapsuleRenderer] # Or your default renderer

    def get_queryset(self):
        user = self.request.user
        queryset = Notification.objects.filter(user=user).order_by('-created_at')
        
        is_read_param = self.request.query_params.get('is_read')
        if is_read_param is not None:
            if is_read_param.lower() == 'true':
                queryset = queryset.filter(is_read=True)
            elif is_read_param.lower() == 'false':
                queryset = queryset.filter(is_read=False)
        return queryset

class NotificationMarkReadView(APIView):
    """
    Mark a specific notification as read.
    """
    permission_classes = [IsAuthenticated]
    renderer_classes = [CapsuleRenderer]

    def post(self, request, pk, *args, **kwargs):
        try:
            notification = Notification.objects.get(pk=pk, user=request.user)
            if not notification.is_read:
                notification.is_read = True
                notification.read_at = timezone.now()
                notification.save(update_fields=['is_read', 'read_at'])
            serializer = NotificationSerializer(notification)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Notification.DoesNotExist:
            return Response({"error": "Notification not found."}, status=status.HTTP_404_NOT_FOUND)

class NotificationMarkAllReadView(APIView):
    """
    Mark all unread notifications for the user as read.
    """
    permission_classes = [IsAuthenticated]
    renderer_classes = [CapsuleRenderer]

    def post(self, request, *args, **kwargs):
        updated_count = Notification.objects.filter(user=request.user, is_read=False).update(is_read=True, read_at=timezone.now())
        return Response({"message": f"{updated_count} notifications marked as read."}, status=status.HTTP_200_OK)

class UnreadNotificationCountView(APIView):
    """
    Get the count of unread notifications for the authenticated user.
    """
    permission_classes = [IsAuthenticated]
    renderer_classes = [CapsuleRenderer] # Or default JSONRenderer

    def get(self, request, *args, **kwargs):
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return Response({'unread_count': count}, status=status.HTTP_200_OK)