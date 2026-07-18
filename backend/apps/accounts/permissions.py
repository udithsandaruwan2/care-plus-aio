"""RBAC + consent permission classes.

RBAC: views declare `allowed_roles = ("admin", ...)`; RolePermission enforces it.
Consent: `HasAIConsent` gates AI processing behind a recorded PDPA/GDPR consent,
raising HTTP 451 (Unavailable For Legal Reasons) when consent is missing.
"""

from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.permissions import BasePermission

from .models import ConsentLog, ConsentScope


class RolePermission(BasePermission):
    """Allow only authenticated users whose role is in ``view.allowed_roles``.

    If a view doesn't set ``allowed_roles``, any authenticated user passes.
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        allowed = getattr(view, "allowed_roles", None)
        if not allowed:
            return True
        return user.role in allowed


def role_required(*roles):
    """Build a permission class restricted to the given roles."""

    class _Scoped(BasePermission):
        def has_permission(self, request, view):
            user = request.user
            return bool(user and user.is_authenticated and user.role in roles)

    _Scoped.__name__ = f"IsRole_{'_'.join(roles)}"
    return _Scoped


IsPatient = role_required("patient")
IsCaregiver = role_required("caregiver")
IsAdmin = role_required("admin")
IsAuditor = role_required("auditor")


class ConsentRequired(APIException):
    """Raised when a required processing consent has not been granted."""

    status_code = status.HTTP_451_UNAVAILABLE_FOR_LEGAL_REASONS
    default_detail = "Processing consent is required before this action."
    default_code = "consent_required"


class HasAIConsent(BasePermission):
    """Require a current ``ai_processing`` consent for the authenticated user.

    Used to gate the voice → intent pipeline (Step 14) so no external AI call is
    ever made without recorded consent. Unauthenticated → 401; authenticated but
    without consent → 451.
    """

    required_scope = ConsentScope.AI_PROCESSING

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if not ConsentLog.is_granted(user, self.required_scope):
            raise ConsentRequired()
        return True
