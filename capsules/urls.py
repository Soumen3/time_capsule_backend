from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CreateCapsuleView, 
    CapsuleDetailView, 
    CapsuleListView, 
    CapsuleViewSet, 
    PublicCapsuleRetrieveView,
    CapsuleDeleteView,
    NotificationListView, # Add this
    NotificationMarkReadView, # Add this
    NotificationMarkAllReadView, # Add this
    UnreadNotificationCountView, # Add this
)

# Define URL patterns for the capsules app
router = DefaultRouter()
router.register(r'capsules', CapsuleViewSet, basename='capsule')

urlpatterns = [
    path('create/', CreateCapsuleView.as_view(), name='create_capsule'),
    path('<int:pk>/', CapsuleDetailView.as_view(), name='capsule_detail'),  # Example detail view for a capsule
    path('', CapsuleListView.as_view(), name='capsule_list'),  # List all capsules for the authenticated user
    path('', include(router.urls)),
    path('public/capsules/<uuid:access_token>/', PublicCapsuleRetrieveView.as_view(), name='public-capsule-detail'),
    path('<int:pk>/delete/', CapsuleDeleteView.as_view(), name='capsule_delete'),  # Add delete URL

    # Notification URLs
    path('notifications/', NotificationListView.as_view(), name='notification-list'),
    path('notifications/unread-count/', UnreadNotificationCountView.as_view(), name='notification-unread-count'),
    path('notifications/<int:pk>/mark-read/', NotificationMarkReadView.as_view(), name='notification-mark-read'),
    path('notifications/mark-all-read/', NotificationMarkAllReadView.as_view(), name='notification-mark-all-read'),
    
    # path('', include(router.urls)), # If using ViewSets
    # path('test-celery/', test_celery_task_view, name='test-celery'), # Example for testing Celery
]
