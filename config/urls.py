from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("django-admin/", admin.site.urls),  # respaldo técnico
    path("", include("asistencia.urls")),
]
