from django.apps import AppConfig


class VocabConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.vocab"
    label = "vocab"
    verbose_name = "Medical vocabulary"
