from django.contrib import admin
from .models import Actividad, Asistencia, Estudiante, FechaClase, Modulo

for m in (Modulo, Estudiante, FechaClase, Asistencia, Actividad):
    admin.site.register(m)
