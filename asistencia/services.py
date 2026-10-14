"""Lógica de negocio. Las vistas solo llaman a estas funciones."""
from django.db import transaction
from django.utils import timezone

from .models import Actividad, Asistencia, Estudiante, FechaClase, Modulo

ETIQUETAS = {
    "PRESENTE": "Presente",
    "FALTA": "Falta",
    "PENDIENTE": "Pendiente",
    "PROGRAMADA": "Programada",
}


def estado_calculado(fecha_clase, registro, hoy):
    """
    RF-04 / RN-05: la falta se calcula, no se guarda.
    - Hay registro  -> su estado.
    - Sin registro y fecha pasada -> FALTA.
    - Sin registro y es hoy -> PENDIENTE (aún puede marcar).
    - Sin registro y fecha futura -> PROGRAMADA.
    """
    if registro:
        return registro.estado
    if fecha_clase.fecha < hoy:
        return Asistencia.FALTA
    if fecha_clase.fecha == hoy:
        return "PENDIENTE"
    return "PROGRAMADA"


def registrar_actividad(modulo, usuario, rol, accion, registro="", anterior="", nuevo=""):
    return Actividad.objects.create(
        modulo=modulo, usuario=usuario, rol=rol, accion=accion,
        registro_afectado=registro, valor_anterior=anterior, valor_nuevo=nuevo,
    )


def marcar_asistencia(estudiante):
    """RF-03. Devuelve (ok, mensaje). Valida en servidor: no basta con ocultar el botón."""
    hoy = timezone.localdate()
    with transaction.atomic():
        clase = FechaClase.objects.filter(modulo=estudiante.modulo, fecha=hoy).first()
        if clase is None:
            return False, "Hoy no hay clase programada. No puedes marcar asistencia."
        ahora = timezone.now()
        asistencia, creada = Asistencia.objects.get_or_create(
            estudiante=estudiante, fecha_clase=clase,
            defaults={"estado": Asistencia.PRESENTE, "marcado_en": ahora},
        )
        if not creada:
            if asistencia.estado == Asistencia.PRESENTE:
                return False, "Ya registraste tu asistencia de hoy."
            return False, "Tu asistencia de hoy ya fue definida por el administrador."
        registrar_actividad(
            estudiante.modulo, str(estudiante), "Estudiante", "Marcó asistencia",
            registro=f"{estudiante} · {clase}", nuevo="Presente",
        )
    hora = timezone.localtime(ahora).strftime("%H:%M:%S")
    return True, f"Asistencia registrada a las {hora}."


def modificar_asistencia(admin_user, estudiante, fecha_clase, nuevo_estado):
    """RF-07 / RN-06 / RN-07. Cambia el estado y deja auditoría en la misma transacción."""
    if nuevo_estado not in (Asistencia.PRESENTE, Asistencia.FALTA):
        return False, "Estado no válido."
    modulo = Modulo.activo_actual()
    if not modulo or estudiante.modulo_id != modulo.id or fecha_clase.modulo_id != modulo.id:
        return False, "El registro no pertenece al módulo activo."

    hoy = timezone.localdate()
    with transaction.atomic():
        registro = Asistencia.objects.filter(estudiante=estudiante, fecha_clase=fecha_clase).first()
        anterior = estado_calculado(fecha_clase, registro, hoy)
        if anterior == nuevo_estado:
            return False, "El estado ya era ese; no hubo cambios."

        if registro is None:
            registro = Asistencia(estudiante=estudiante, fecha_clase=fecha_clase)
        registro.estado = nuevo_estado
        registro.modificado_por_admin = True
        if nuevo_estado == Asistencia.FALTA:
            registro.marcado_en = None
        registro.save()

        registrar_actividad(
            modulo, admin_user.get_username(), "Administrador", "Modificó asistencia",
            registro=f"{estudiante} · {fecha_clase}",
            anterior=ETIQUETAS[anterior], nuevo=ETIQUETAS[nuevo_estado],
        )
    return True, f"Asistencia actualizada: {estudiante.nombre} → {ETIQUETAS[nuevo_estado]}."


def activar_modulo(admin_user, nombre, estudiantes, fechas):
    """
    RF-13 / RN-08. Todo o nada: desactiva el módulo anterior (sin borrarlo)
    y crea el nuevo con sus estudiantes y fechas.
    """
    with transaction.atomic():
        Modulo.objects.filter(activo=True).update(activo=False)
        modulo = Modulo.objects.create(nombre=nombre, activo=True)
        Estudiante.objects.bulk_create([
            Estudiante(modulo=modulo, nro_registro=e["nro_registro"],
                       nombre=e["nombre"], correo=e["correo"].lower())
            for e in estudiantes
        ])
        from datetime import date, time
        FechaClase.objects.bulk_create([
            FechaClase(
                modulo=modulo,
                fecha=date.fromisoformat(f["fecha"]),
                hora_inicio=time.fromisoformat(f["inicio"]),
                hora_fin=time.fromisoformat(f["fin"]),
            )
            for f in fechas
        ])
        registrar_actividad(
            modulo, admin_user.get_username(), "Administrador", "Activó nuevo módulo",
            registro=f"{nombre} ({len(estudiantes)} estudiantes, {len(fechas)} fechas)",
        )
    return modulo


def habilitar_modulo(admin_user, modulo):
    """Vuelve a activar un módulo existente. El que estaba activo queda inactivo (RN-01)."""
    with transaction.atomic():
        Modulo.objects.filter(activo=True).exclude(pk=modulo.pk).update(activo=False)
        modulo.activo = True
        modulo.save(update_fields=["activo"])
        registrar_actividad(modulo, admin_user.get_username(), "Administrador",
                            "Habilitó módulo", registro=modulo.nombre)


def deshabilitar_modulo(admin_user, modulo):
    """Desactiva el módulo sin borrar nada. Mientras no haya uno activo, nadie puede marcar."""
    with transaction.atomic():
        modulo.activo = False
        modulo.save(update_fields=["activo"])
        registrar_actividad(modulo, admin_user.get_username(), "Administrador",
                            "Deshabilitó módulo", registro=modulo.nombre)


def eliminar_modulo(admin_user, modulo, nombre_confirmado):
    """
    Borrado DEFINITIVO de un módulo y todo lo que cuelga de él.
    Protecciones: no se puede eliminar el módulo activo y hay que escribir su nombre exacto.
    """
    if modulo.activo:
        return False, "No se puede eliminar un módulo habilitado. Deshabilítalo primero."
    if (nombre_confirmado or "").strip() != modulo.nombre:
        return False, "El nombre escrito no coincide. No se eliminó nada."
    nombre = modulo.nombre
    with transaction.atomic():
        n_est = modulo.estudiantes.count()
        n_fec = modulo.fechas.count()
        Actividad.objects.filter(modulo=modulo).delete()
        modulo.delete()  # borra en cascada estudiantes, fechas y asistencias
        registrar_actividad(None, admin_user.get_username(), "Administrador", "Eliminó módulo",
                            registro=f"{nombre} ({n_est} estudiantes, {n_fec} fechas)")
    return True, f"Módulo «{nombre}» eliminado definitivamente."
