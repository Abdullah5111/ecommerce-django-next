from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Project-level app: registers the deployment checks in core/checks.py."""

    name = "core"

    def ready(self):
        # Imported for its @register side effect.
        from . import checks  # noqa: F401
