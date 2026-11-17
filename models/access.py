# -*- coding: utf-8 -*-
"""Module capability checks, deliberately independent of Odoo administration."""
from odoo import _
from odoo.exceptions import AccessError

BPI_GROUP = 'bader_product_intelligence.group_bpi_user'
BPI_GROUPS = 'base.group_system,' + BPI_GROUP
# An RPC context can contain strings/booleans, never this in-process identity.
_BPI_JOB_CREATE = object()


def _active_internal_user(env):
    user = env.user
    return bool(user.active and not user.share and user.has_group('base.group_user')
                and not user.has_group('base.group_portal')
                and not user.has_group('base.group_public'))


def has_bpi_admin_access(env):
    # Trusted ORM superuser mode is used by cron, installation and explicit
    # public projections. It is not a client-supplied context flag. OdooBot
    # itself can be inactive; ordinary with_user(inactive) remains denied.
    return bool(env.su or (_active_internal_user(env) and env.user.has_group('base.group_system')))


def has_bpi_access(env):
    return bool(env.su or (_active_internal_user(env) and (
        env.user.has_group('base.group_system') or env.user.has_group(BPI_GROUP))))


def ensure_bpi_access(env):
    if not has_bpi_access(env):
        raise AccessError(_('Producto Intelligence requiere acceso al módulo para un usuario interno activo.'))


def ensure_bpi_admin(env):
    if not has_bpi_admin_access(env):
        raise AccessError(_('Esta configuración de Producto Intelligence requiere permisos de administrador.'))
