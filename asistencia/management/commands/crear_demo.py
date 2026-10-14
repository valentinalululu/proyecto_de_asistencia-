from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from asistencia.models import Asistencia, Estudiante
from asistencia.services import activar_modulo

NOMBRES = ["Juan Pérez", "María López", "Carlos Rojas", "Ana Flores", "Luis Mamani", "Sofía Vargas",
           "Diego Cruz", "Lucía Ribera", "Marco Suárez", "Valeria Justiniano", "Pablo Egüez", "Camila Soliz"]


class Command(BaseCommand):
    help = "Crea el administrador (admin / admin1234) y un módulo de demostración."

    def handle(self, *args, **opts):
        User = get_user_model()
        admin, creado = User.objects.get_or_create(username="admin", defaults={"is_staff": True, "is_superuser": True})
        if creado:
            admin.set_password("admin1234")
            admin.save()

        hoy = timezone.localdate()
        estudiantes = [{"nro_registro": str(1001 + i), "nombre": n,
                        "correo": f"{n.split()[0].lower().replace('í','i').replace('ú','u')}@gmail.com"}
                       for i, n in enumerate(NOMBRES)]
        fechas = [{"fecha": (hoy + timedelta(days=d)).isoformat(), "inicio": "18:00", "fin": "21:00"}
                  for d in (-4, -2, 0, 2, 4)]
        modulo = activar_modulo(admin, "Módulo Demo", estudiantes, fechas)

        # Algunas asistencias pasadas para que el historial no esté vacío
        pasadas = list(modulo.fechas.filter(fecha__lt=hoy))
        for i, est in enumerate(Estudiante.objects.filter(modulo=modulo)):
            for j, f in enumerate(pasadas):
                if (i + j) % 3 != 0:
                    Asistencia.objects.create(estudiante=est, fecha_clase=f, estado="PRESENTE",
                                              marcado_en=timezone.now() - timedelta(days=4 - 2 * j))
        self.stdout.write(self.style.SUCCESS(
            "Listo. Admin: admin / admin1234 · Estudiante: usa 1001 o juan@gmail.com"))
