"""JWT auth for Channels WebSockets (query ``?token=<access>``)."""

from __future__ import annotations

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser


@database_sync_to_async
def _user_from_token(token: str):
    from rest_framework_simplejwt.tokens import AccessToken

    try:
        access = AccessToken(token)
        return get_user_model().objects.get(pk=access["user_id"])
    except Exception:
        return AnonymousUser()


class JwtAuthMiddleware(BaseMiddleware):
    """Populate ``scope["user"]`` from a JWT access token in the query string."""

    async def __call__(self, scope, receive, send):
        query = parse_qs((scope.get("query_string") or b"").decode())
        raw = (query.get("token") or [None])[0]
        scope["user"] = await _user_from_token(raw) if raw else AnonymousUser()
        return await super().__call__(scope, receive, send)


def JwtAuthMiddlewareStack(inner):
    return JwtAuthMiddleware(inner)
