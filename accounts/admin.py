from django.contrib import admin
from .models import User

# Register your models here.
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('id', 'email', 'name', 'dob', 'is_active', 'is_staff', 'updated_at')
    list_display_links = ('id', 'email')
    search_fields = ('email', 'name')
    list_filter = ('is_active', 'is_staff')
    # ordering = ('-created_at',)
    fieldsets = (
        (None, {
            'fields': ('email', 'name', 'dob', 'password', 'otp', 'otp_created_at')
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at',)
        }),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'name', 'dob', 'password1', 'password2')
        }),
    )
    readonly_fields = ('created_at', 'updated_at', 'password',)
