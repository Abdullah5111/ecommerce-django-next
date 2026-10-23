from django.urls import path

from .views import MessagesView, ThreadsView, ThreadView

urlpatterns = [
    path("chat/thread/", ThreadView.as_view()),
    path("chat/messages/", MessagesView.as_view()),
    path("chat/threads/", ThreadsView.as_view()),
]
