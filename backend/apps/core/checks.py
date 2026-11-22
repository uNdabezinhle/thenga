"""Django system checks for deploy safety."""
from django.conf import settings
from django.core.checks import Error, Tags, Warning, register


@register(Tags.security, deploy=True)
def check_debug_off_in_deploy(app_configs, **kwargs):
    errors = []
    if settings.DEBUG:
        errors.append(
            Error(
                "DEBUG is True while running deploy checks.",
                hint="Set DJANGO_DEBUG=false in production.",
                id="reka.E001",
            )
        )
    return errors


@register(Tags.security)
def check_secret_key_strength(app_configs, **kwargs):
    warnings = []
    key = settings.SECRET_KEY or ""
    if key.startswith("dev-") or "change-me" in key or len(key) < 32:
        warnings.append(
            Warning(
                "DJANGO_SECRET_KEY looks weak or default.",
                hint="Use a long random secret in any shared environment.",
                id="reka.W001",
            )
        )
    return warnings
