# Sistema web de registro y control de asistencia (Django)

## Puesta en marcha en Visual Studio Code

```bash
# 1. Abre la carpeta del proyecto en VS Code y una terminal (Ctrl+ñ)
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux / macOS

pip install -r requirements.txt
python manage.py migrate
python manage.py crear_demo          # admin + módulo de demostración
python manage.py runserver
```

- Estudiantes: http://127.0.0.1:8000/ → usa `1001` o `juan@gmail.com`
- Administrador: http://127.0.0.1:8000/panel/login/ → `admin` / `admin1234`

Pruebas automáticas: `python manage.py test`

## Datos para la demo
`python manage.py generar_ejemplos` crea en `/ejemplos` los Excel de prueba
(la primera fecha de clase es **hoy**):
`estudiantes_ejemplo.xlsx`, `fechas_ejemplo.xlsx` y `estudiantes_con_errores.xlsx`.

## Estructura
| Archivo | Qué contiene |
|---|---|
| `asistencia/models.py` | Modelo de datos y restricciones únicas (RN-01, RN-02, RN-03) |
| `asistencia/services.py` | Reglas de negocio: marcar, calcular faltas, modificar con auditoría, activar módulo |
| `asistencia/importers.py` | Lectura y validación de los Excel |
| `asistencia/views.py` | Pantallas de estudiante y administrador |
| `templates/` | Interfaz (Bootstrap 5) |
| `asistencia/tests.py` | Pruebas de las reglas clave |

## Decisiones de diseño
- La **falta se calcula**: no se guarda un registro por cada ausencia.
- Zona horaria `America/La_Paz` en `config/settings.py`.
- El reinicio de módulo **nunca borra**: marca el anterior como inactivo (transacción atómica).
- Se valida en el servidor que solo se marque el día de clase.
- Los correos también deben ser únicos por módulo, para que el acceso por correo no sea ambiguo.
- Limitación conocida: el estudiante entra sin contraseña (como pide el documento).
