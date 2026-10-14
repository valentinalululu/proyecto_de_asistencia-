from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from openpyxl import Workbook

from config.settings import BASE_DIR

NOMBRES = ["Juan Pérez", "María López", "Carlos Rojas", "Ana Flores", "Luis Mamani", "Sofía Vargas",
           "Diego Cruz", "Lucía Ribera", "Marco Suárez", "Valeria Justiniano"]


def _guardar(nombre, cabecera, filas):
    wb = Workbook()
    ws = wb.active
    ws.append(cabecera)
    for f in filas:
        ws.append(f)
    ruta = BASE_DIR / "ejemplos" / nombre
    wb.save(ruta)
    return ruta


class Command(BaseCommand):
    help = "Genera los Excel de ejemplo en /ejemplos (la primera fecha de clase es HOY)."

    def handle(self, *args, **opts):
        hoy = timezone.localdate()
        estudiantes = [[str(2001 + i), n, n.split()[0].lower().replace("í", "i").replace("ú", "u") + "@gmail.com"]
                       for i, n in enumerate(NOMBRES)]
        fechas = [[(hoy + timedelta(days=2 * i)).strftime("%d/%m/%Y"), "18:00", "21:00"] for i in range(4)]
        _guardar("estudiantes_ejemplo.xlsx", ["Número de registro", "Nombre completo", "Correo electrónico"], estudiantes)
        _guardar("fechas_ejemplo.xlsx", ["Fecha", "Hora inicio", "Hora fin"], fechas)
        con_errores = [list(f) for f in estudiantes]
        con_errores[2][2] = "correo-sin-arroba"      # correo inválido
        con_errores[4][0] = con_errores[0][0]        # registro duplicado
        con_errores[6][1] = ""                       # nombre faltante
        _guardar("estudiantes_con_errores.xlsx", ["Número de registro", "Nombre completo", "Correo electrónico"], con_errores)
        self.stdout.write(self.style.SUCCESS("Excel de ejemplo generados en la carpeta /ejemplos"))
