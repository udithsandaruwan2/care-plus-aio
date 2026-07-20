from django.urls import path

from .views import LeadContactView, LeadListCreateView

urlpatterns = [
    path("leads/", LeadListCreateView.as_view(), name="lead_list"),
    path("leads/<int:pk>/contact/", LeadContactView.as_view(), name="lead_contact"),
]
