from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from .models import Estudiante


def estudiante_required(view):
    @wraps(view)
    def _wrapped(request, *args, **kwargs):
        eid = request.session.get("estudiante_id")
        if not eid:
            return redirect("login_estudiante")
        est = Estudiante.objects.select_related("modulo").filter(pk=eid, modulo__activo=True).first()
        if est is None:  # el módulo cambió: la sesión ya no es válida
            request.session.flush()
            messages.error(request, "Tu sesión ya no es válida. Ingresa nuevamente.")
            return redirect("login_estudiante")
        request.estudiante = est
        return view(request, *args, **kwargs)
    return _wrapped


def admin_required(view):
    """RF-02: funciones administrativas restringidas al rol administrador."""
    @wraps(view)
    def _wrapped(request, *args, **kwargs):
        if not (request.user.is_authenticated and request.user.is_staff):
            return redirect("login_admin")
        return view(request, *args, **kwargs)
    return _wrapped
