from django.urls import path

from .views import AdminConditionDetailView, AdminConditionListCreateView, ConditionListView

urlpatterns = [
    path("vocab/conditions/", ConditionListView.as_view(), name="vocab_conditions"),
    path(
        "admin/vocab/conditions/",
        AdminConditionListCreateView.as_view(),
        name="admin_vocab_conditions",
    ),
    path(
        "admin/vocab/conditions/<slug:slug>/",
        AdminConditionDetailView.as_view(),
        name="admin_vocab_condition_detail",
    ),
]
