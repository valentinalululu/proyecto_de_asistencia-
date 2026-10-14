from datetime import timedelta
from io import BytesIO

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from openpyxl import Workbook

from .importers import parse_estudiantes, parse_fechas
from .models import Actividad, Asistencia, Estudiante, Modulo
from .services import activar_modulo, marcar_asistencia, modificar_asistencia


def _xlsx(cabecera, filas):
    wb = Workbook()
    wb.active.append(cabecera)
    for f in filas:
        wb.active.append(f)
    b = BytesIO()
    wb.save(b)
    b.seek(0)
    return b


class BaseConDatos(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user("admin", password="x", is_staff=True)
        hoy = timezone.localdate()
        self.modulo = activar_modulo(
            self.admin, "M1",
            [{"nro_registro": "1001", "nombre": "Juan", "correo": "juan@gmail.com"}],
            [{"fecha": (hoy - timedelta(days=2)).isoformat(), "inicio": "18:00", "fin": "21:00"},
             {"fecha": hoy.isoformat(), "inicio": "18:00", "fin": "21:00"},
             {"fecha": (hoy + timedelta(days=2)).isoformat(), "inicio": "18:00", "fin": "21:00"}],
        )
        self.est = Estudiante.objects.get(nro_registro="1001")


class AsistenciaTests(BaseConDatos):
    def test_marca_una_sola_vez(self):
        ok, _ = marcar_asistencia(self.est)
        ok2, _ = marcar_asistencia(self.est)
        self.assertTrue(ok)
        self.assertFalse(ok2)
        self.assertEqual(Asistencia.objects.count(), 1)

    def test_no_marca_sin_clase_hoy(self):
        self.modulo.fechas.filter(fecha=timezone.localdate()).delete()
        ok, _ = marcar_asistencia(self.est)
        self.assertFalse(ok)

    def test_admin_corrige_falta_pasada_con_auditoria(self):
        pasada = self.modulo.fechas.first()
        ok, _ = modificar_asistencia(self.admin, self.est, pasada, "PRESENTE")
        self.assertTrue(ok)
        log = Actividad.objects.filter(accion="Modificó asistencia").first()
        self.assertEqual((log.valor_anterior, log.valor_nuevo), ("Falta", "Presente"))

    def test_nuevo_modulo_conserva_el_anterior(self):
        activar_modulo(self.admin, "M2", [{"nro_registro": "1", "nombre": "A", "correo": "a@a.com"}],
                       [{"fecha": timezone.localdate().isoformat(), "inicio": "18:00", "fin": "21:00"}])
        self.assertEqual(Modulo.objects.filter(activo=True).count(), 1)
        self.assertTrue(Estudiante.objects.filter(modulo=self.modulo).exists())

    def test_login_estudiante_por_correo_y_registro(self):
        for dato in ("juan@gmail.com", "1001"):
            self.client.logout()
            r = self.client.post(reverse("login_estudiante"), {"identificador": dato})
            self.assertRedirects(r, reverse("mi_asistencia"))
        self.client.logout()
        r = self.client.post(reverse("login_estudiante"), {"identificador": "9999"})
        self.assertEqual(r.status_code, 200)

    def test_estudiante_no_accede_al_panel(self):
        self.client.post(reverse("login_estudiante"), {"identificador": "1001"})
        r = self.client.get(reverse("actividades"))
        self.assertRedirects(r, reverse("login_admin"))

    def test_importador_reporta_errores(self):
        f = _xlsx(["a", "b", "c"], [[1001, "Ana", "ana@x.com"], [1001, "Beto", "malo"], [1003, "", "c@x.com"]])
        datos, errores = parse_estudiantes(f)
        self.assertEqual(len(datos), 1)
        self.assertEqual(len(errores), 2)

    def test_importador_fechas(self):
        f = _xlsx(["Fecha", "i", "f"], [["05/10/2026", "18:00", "21:00"], ["xx", "18:00", "21:00"]])
        datos, errores = parse_fechas(f)
        self.assertEqual(datos[0]["fecha"], "2026-10-05")
        self.assertEqual(len(errores), 1)


class ModulosTests(BaseConDatos):
    def _admin(self):
        self.client.login(username="admin", password="x")

    def test_habilitar_otro_modulo_deja_uno_solo_activo(self):
        m2 = activar_modulo(self.admin, "M2", [{"nro_registro": "1", "nombre": "A", "correo": "a@a.com"}],
                            [{"fecha": timezone.localdate().isoformat(), "inicio": "18:00", "fin": "21:00"}])
        self._admin()
        self.client.post(reverse("modulo_habilitar", args=[self.modulo.id]))
        self.assertEqual(list(Modulo.objects.filter(activo=True)), [self.modulo])
        m2.refresh_from_db()
        self.assertFalse(m2.activo)

    def test_deshabilitar_deja_sin_modulo_activo_y_sin_borrar(self):
        self._admin()
        self.client.post(reverse("modulo_deshabilitar", args=[self.modulo.id]))
        self.assertEqual(Modulo.objects.filter(activo=True).count(), 0)
        self.assertTrue(Estudiante.objects.filter(modulo=self.modulo).exists())
        self.client.logout()
        r = self.client.post(reverse("login_estudiante"), {"identificador": "1001"})
        self.assertEqual(r.status_code, 200)  # no puede ingresar

    def test_pantalla_modulos_y_paneles_sin_modulo(self):
        self._admin()
        self.client.post(reverse("modulo_deshabilitar", args=[self.modulo.id]))
        self.assertEqual(self.client.get(reverse("modulos")).status_code, 200)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)
        self.assertRedirects(self.client.get(reverse("asistencias")), reverse("modulos"))

    def test_estudiante_no_puede_cambiar_modulos(self):
        self.client.post(reverse("login_estudiante"), {"identificador": "1001"})
        r = self.client.post(reverse("modulo_deshabilitar", args=[self.modulo.id]))
        self.assertRedirects(r, reverse("login_admin"))
        self.assertTrue(Modulo.objects.get(pk=self.modulo.pk).activo)


class EliminarModuloTests(BaseConDatos):
    def setUp(self):
        super().setUp()
        self.m2 = activar_modulo(self.admin, "M2", [{"nro_registro": "1", "nombre": "A", "correo": "a@a.com"}],
                                 [{"fecha": timezone.localdate().isoformat(), "inicio": "18:00", "fin": "21:00"}])
        self.client.login(username="admin", password="x")

    def test_no_elimina_modulo_activo(self):
        self.client.post(reverse("modulo_eliminar", args=[self.m2.id]), {"confirmacion": "M2"})
        self.assertTrue(Modulo.objects.filter(pk=self.m2.pk).exists())

    def test_no_elimina_con_nombre_incorrecto(self):
        self.client.post(reverse("modulo_eliminar", args=[self.modulo.id]), {"confirmacion": "otro"})
        self.assertTrue(Modulo.objects.filter(pk=self.modulo.pk).exists())

    def test_elimina_inactivo_con_nombre_correcto_y_en_cascada(self):
        self.client.post(reverse("modulo_eliminar", args=[self.modulo.id]), {"confirmacion": "M1"})
        self.assertFalse(Modulo.objects.filter(pk=self.modulo.pk).exists())
        self.assertFalse(Estudiante.objects.filter(nro_registro="1001").exists())
        self.assertTrue(Modulo.objects.filter(pk=self.m2.pk, activo=True).exists())
        self.assertTrue(Actividad.objects.filter(accion="Eliminó módulo").exists())
