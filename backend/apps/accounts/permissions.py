"""RBAC permission classes.

Views declare `allowed_roles = ("admin", ...)`. RolePermission enforces it.
Convenience subclasses cover the common single-role cases.
"""

from rest_framework.permissions import BasePermission


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
