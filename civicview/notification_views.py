# In-app notifications: list and mark read (authenticated user only)
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework.permissions import IsAuthenticated

from .models import Notification
from .serializers import NotificationSerializer


class NotificationListView(APIView):
    """GET /api/notifications/ - List current user's notifications (newest first)."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request):
        qs = Notification.objects.filter(user=request.user).select_related("report")[:50]
        serializer = NotificationSerializer(qs, many=True)
        return Response(serializer.data)


class NotificationMarkReadView(APIView):
    """PATCH /api/notifications/{id}/read/ - Mark one notification as read."""

    permission_classes = [IsAuthenticated]

    def patch(self, request: Request, pk=None):
        from django.utils import timezone
        notification = Notification.objects.filter(user=request.user, pk=pk).first()
        if not notification:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at"])
        return Response(NotificationSerializer(notification).data)
