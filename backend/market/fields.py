"""Custom encrypted model field using Fernet symmetric encryption."""

from django.db import models

from core.encryption import decrypt_value, encrypt_value


class EncryptedTextField(models.TextField):
    """TextField that transparently encrypts on save and decrypts on read."""

    def get_prep_value(self, value):
        if value is None or value == "":
            return value
        return encrypt_value(value)

    def from_db_value(self, value, expression, connection):
        if value is None or value == "":
            return value
        return decrypt_value(value)
