from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Authentication and the custom User model shared by all four roles."""

    name = "apps.accounts"
    # Short label keeps model references stable, e.g. "accounts.ModelName".
    label = "accounts"
    verbose_name = "Accounts"
