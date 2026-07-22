from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role

from .models import Message
from .push import push_message_created, push_messages_read
from .serializers import (
    MessageCreateSerializer,
    MessageReadSerializer,
    MessageSerializer,
    MessageThreadSerializer,
)
from .services import (
    current_thread_for_user,
    get_thread_for_user,
    mark_messages_read,
    send_message,
)


class MessageThreadCurrentView(APIView):
    """GET /message-threads/current/ — thread for active primary care link."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        role = getattr(request.user, "role", None)
        if role not in (Role.PATIENT, Role.CAREGIVER):
            raise PermissionDenied("Only patients and caregivers can use messaging.")
        thread = current_thread_for_user(request.user)
        if thread is None:
            return Response(None)
        return Response(MessageThreadSerializer(thread, context={"request": request}).data)


class MessageListCreateView(generics.ListCreateAPIView):
    """GET/POST /message-threads/<id>/messages/ — list (polling) or send."""

    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return MessageCreateSerializer
        return MessageSerializer

    def get_thread(self):
        if not hasattr(self, "_thread"):
            self._thread = get_thread_for_user(self.request.user, self.kwargs["pk"])
        return self._thread

    def get_queryset(self):
        thread = self.get_thread()
        qs = Message.objects.filter(thread=thread).select_related("sender")
        after_id = (self.request.query_params.get("after_id") or "").strip()
        if after_id.isdigit():
            qs = qs.filter(pk__gt=int(after_id))
        limit = (self.request.query_params.get("limit") or "50").strip()
        try:
            n = min(max(int(limit), 1), 100)
        except ValueError:
            n = 50
        return qs.order_by("created_at")[:n]

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = MessageSerializer(
            queryset, many=True, context={"request": request}
        )
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        ser = MessageCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        thread = self.get_thread()
        try:
            message = send_message(
                thread=thread,
                sender=request.user,
                body=ser.validated_data["body"],
            )
        except PermissionDenied:
            raise
        except DRFValidationError:
            raise
        except Exception as exc:
            raise DRFValidationError(str(exc)) from exc

        out = MessageSerializer(message, context={"request": request}).data
        push_message_created(thread.pk, out)
        return Response(out, status=status.HTTP_201_CREATED)


class MessageReadView(APIView):
    """POST /message-threads/<id>/read/ — mark messages read up to id."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk: int):
        ser = MessageReadSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        thread = get_thread_for_user(request.user, pk)
        try:
            count = mark_messages_read(
                thread=thread,
                reader=request.user,
                last_read_message_id=ser.validated_data["last_read_message_id"],
            )
        except PermissionDenied:
            raise
        except DRFValidationError:
            raise
        except Exception as exc:
            raise DRFValidationError(str(exc)) from exc

        payload = {
            "thread_id": thread.pk,
            "last_read_message_id": ser.validated_data["last_read_message_id"],
            "reader_id": request.user.pk,
            "updated_count": count,
        }
        push_messages_read(thread.pk, payload)
        return Response(payload)
