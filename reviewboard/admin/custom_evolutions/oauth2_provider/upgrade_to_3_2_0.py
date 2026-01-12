"""Upgrade oauth2_provider from 1.6.3 to 3.2.0.

This is roughly equivalent to the following migrations in oauth2_provider
3.2.0:

* ``0006_alter_application_client_secret``
* ``0007_application_post_logout_redirect_uris``
* ``0008_alter_accesstoken_token``
* ``0009_add_hash_client_secret``
* ``0010_application_allowed_origins``
* ``0011_refreshtoken_token_family``
* ``0012_add_token_checksum``
* ``0013_alter_application_authorization_grant_type_device``

These migrations are recorded in
:py:func:`~reviewboard.upgrade.post_upgrade_reset_oauth2_provider`.

Version Added:
    8.0
"""

from __future__ import annotations

from django.db import models
from django_evolution.mutations import AddField, ChangeField
from oauth2_provider.models import TokenChecksumField


MUTATIONS = [
    # Changes to the oauth2_provider_application table.
    AddField('Application', 'allowed_origins', models.TextField,
             initial=''),
    AddField('Application', 'hash_client_secret', models.BooleanField,
             initial=True),
    AddField('Application', 'post_logout_redirect_uris', models.TextField,
             initial=''),
    ChangeField('Application', 'authorization_grant_type', max_length=44),

    # Changes to the oauth2_provider_accesstoken table.
    AddField('AccessToken', 'token_checksum', TokenChecksumField,
             max_length=64, db_index=True, initial='', unique=True),
    ChangeField('AccessToken', 'token', field_type=models.TextField),

    # Changes to the oauth2_provider_refreshtoken table.
    AddField('RefreshToken', 'token_family', models.UUIDField, null=True,
             max_length=32),
]
