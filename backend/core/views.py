from django.http import JsonResponse


def health(request):
    """Lightweight liveness probe for deploy/uptime checks. Public, no DB hit."""
    return JsonResponse({"status": "ok"})
