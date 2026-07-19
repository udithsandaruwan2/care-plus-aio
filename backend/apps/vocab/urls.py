from django.urls import path

from .views import ConditionListView

urlpatterns = [
    path("vocab/conditions/", ConditionListView.as_view(), name="vocab_conditions"),
]
