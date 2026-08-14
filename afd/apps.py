# afd/apps.py
from django.apps import AppConfig


class AfdConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'afd'
    verbose_name = 'Conformidade AFD (Portaria 671/2021)'

    def ready(self):
        from . import signals  # noqa: F401
