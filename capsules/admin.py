from django.contrib import admin
from .models import Capsule, CapsuleContent, CapsuleRecipient, DeliveryLog, Notification

# Register your models here.

@admin.register(Capsule)
class CapsuleAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'title', 'owner', 'creation_date', 'delivery_date', 'is_delivered', 'privacy_status', 'is_archived'
    )
    list_filter = ('is_delivered', 'privacy_status', 'is_archived', 'delivery_method')
    search_fields = ('title', 'owner__email', 'owner__name')
    date_hierarchy = 'delivery_date'
    ordering = ('-delivery_date',)
    fieldsets = (
        (None, {
            'fields': ('title', 'owner', 'description', 'creation_date', 'delivery_date', 'delivery_time', 'is_delivered', 'is_archived')
        }),
        ('Delivery Options', {
            'fields': ('delivery_method', 'privacy_status')
        }),
        ('Legacy Management', {
            'fields': ('transfer_on_inactivity', 'transfer_recipient_email')
        }),
    )
    raw_id_fields = ('owner',)

@admin.register(CapsuleContent)
class CapsuleContentAdmin(admin.ModelAdmin):
    list_display = ('id', 'capsule', 'content_type', 'upload_date', 'order')
    list_filter = ('content_type',)
    search_fields = ('capsule__title',)
    ordering = ('capsule', 'order')

@admin.register(CapsuleRecipient)
class CapsuleRecipientAdmin(admin.ModelAdmin):
    list_display = (
        'id', 
        'capsule_title', 
        'recipient_email', 
        'received_status', 
        'sent_date', 
        'access_token', # Add access_token here
        'token_generated_at' # Add token_generated_at here
    )
    list_filter = ('received_status', 'capsule__delivery_date')
    search_fields = ('recipient_email', 'capsule__title')
    readonly_fields = ('access_token', 'token_generated_at', 'sent_date') # Make token fields read-only

    def capsule_title(self, obj):
        return obj.capsule.title
    capsule_title.short_description = 'Capsule Title' # Column header

@admin.register(DeliveryLog)
class DeliveryLogAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'capsule', 'delivery_attempt_time', 'delivery_method', 'recipient_email', 'recipient_user', 'status'
    )
    list_filter = ('delivery_method', 'status')
    search_fields = ('capsule__title', 'recipient_email', 'recipient_user__email')
    ordering = ('-delivery_attempt_time',)

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'user', 'capsule', 'notification_type', 'is_read', 'created_at', 'read_at'
    )
    list_filter = ('notification_type', 'is_read')
    search_fields = ('user__email', 'capsule__title', 'message')
    ordering = ('-created_at',)
