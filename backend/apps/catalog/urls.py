from django.urls import path

from .views import AddOnListView, CarePackageListView

urlpatterns = [
    path("catalog/packages/", CarePackageListView.as_view(), name="catalog_packages"),
    path("catalog/addons/", AddOnListView.as_view(), name="catalog_addons"),
]
