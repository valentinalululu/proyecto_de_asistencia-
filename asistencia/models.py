from django.db import models
from django.db.models import Q


class Modulo(models.Model):
    """Un módulo académico. Todo lo demás cuelga de aquí (RF-15, RN-08)."""

    nombre = models.CharField(max_length=120)
    activo = models.BooleanField(default=False)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # RN-01: solo un módulo activo a la vez (garantizado por la BD).
            models.UniqueConstraint(
                fields=["activo"],
                condition=Q(activo=True),
                name="un_solo_modulo_activo",
            )
        ]

    def __str__(self):
        return self.nombre

    @classmethod
    def activo_actual(cls):
        return cls.objects.filter(activo=True).first()


class Estudiante(models.Model):
    modulo = models.ForeignKey(Modulo, on_delete=models.CASCADE, related_name="estudiantes")
    nro_registro = models.CharField("número de registro", max_length=30)
    nombre = models.CharField("nombre completo", max_length=150)
    correo = models.EmailField("correo electrónico")

    class Meta:
        constraints = [
            # RN-02
            models.UniqueConstraint(fields=["modulo", "nro_registro"], name="registro_unico_por_modulo"),
            models.UniqueConstraint(fields=["modulo", "correo"], name="correo_unico_por_modulo"),
        ]
        ordering = ["nombre"]

    def save(self, *args, **kwargs):
        self.correo = self.correo.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nro_registro} - {self.nombre}"


class FechaClase(models.Model):
    modulo = models.ForeignKey(Modulo, on_delete=models.CASCADE, related_name="fechas")
    fecha = models.DateField()
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["modulo", "fecha"], name="fecha_unica_por_modulo")]
        ordering = ["fecha"]

    def __str__(self):
        return self.fecha.strftime("%d/%m/%Y")


class Asistencia(models.Model):
    """
    Solo existe un registro cuando el estudiante marcó o cuando el admin corrigió.
    La 'Falta' por no marcar NO se guarda: se calcula (ver services.estado_calculado).
    """

    PRESENTE = "PRESENTE"
    FALTA = "FALTA"
    ESTADOS = [(PRESENTE, "Presente"), (FALTA, "Falta")]

    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name="asistencias")
    fecha_clase = models.ForeignKey(FechaClase, on_delete=models.CASCADE, related_name="asistencias")
    estado = models.CharField(max_length=10, choices=ESTADOS)
    marcado_en = models.DateTimeField(null=True, blank=True)  # fecha y hora reales de la marca
    modificado_por_admin = models.BooleanField(default=False)

    class Meta:
        constraints = [
            # RN-03: una sola marca por estudiante y fecha
            models.UniqueConstraint(fields=["estudiante", "fecha_clase"], name="una_marca_por_fecha")
        ]


class Actividad(models.Model):
    """Historial de acciones (RF-09)."""

    modulo = models.ForeignKey(Modulo, on_delete=models.SET_NULL, null=True, related_name="actividades")
    usuario = models.CharField(max_length=200)
    rol = models.CharField(max_length=20)
    accion = models.CharField(max_length=60)
    fecha_hora = models.DateTimeField(auto_now_add=True)
    registro_afectado = models.CharField(max_length=250, blank=True)
    valor_anterior = models.CharField(max_length=100, blank=True)
    valor_nuevo = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["-fecha_hora", "-id"]
        verbose_name_plural = "actividades"
