from django.contrib import admin

from .models import ChatMessage, ChatThread


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(ChatThread)
class ChatThreadAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "created_at")
    search_fields = ("user__username", "user__email")
    inlines = (ChatMessageInline,)


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "thread", "sender", "created_at")
    readonly_fields = ("created_at",)
    list_filter = ("created_at",)
