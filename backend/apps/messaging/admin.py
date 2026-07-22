from django.contrib import admin

from .models import Message, MessageThread

admin.site.register(MessageThread)
admin.site.register(Message)
