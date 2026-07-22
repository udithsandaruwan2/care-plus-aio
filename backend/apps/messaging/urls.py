from django.urls import path

from .views import MessageListCreateView, MessageReadView, MessageThreadCurrentView

urlpatterns = [
    path(
        "message-threads/current/",
        MessageThreadCurrentView.as_view(),
        name="message_thread_current",
    ),
    path(
        "message-threads/<int:pk>/messages/",
        MessageListCreateView.as_view(),
        name="message_list_create",
    ),
    path(
        "message-threads/<int:pk>/read/",
        MessageReadView.as_view(),
        name="message_read",
    ),
]
