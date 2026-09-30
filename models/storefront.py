# -*- coding: utf-8 -*-
"""Opt-in presentation only. No catalog, price or media ownership changes."""
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError
from odoo.tools import html2plaintext


STOREFRONT_FIELDS = frozenset({
    'bpi_premium_storefront_enabled', 'bpi_premium_footer_html',
    'bpi_premium_footer_legal_name',
})


class Website(models.Model):
    _inherit = 'website'

    bpi_premium_storefront_enabled = fields.Boolean(
        string='Diseño Bader: ficha y pie de página', default=False, copy=False)
    # A product-independent, website-owned field lets the native website editor
    # save authored footer content without overwriting a module template.
    bpi_premium_footer_html = fields.Html(
        string='Contenido del pie Bader', translate=True, sanitize=True,
        sanitize_style=True, copy=False)
    bpi_premium_footer_legal_name = fields.Char(
        string='Razón social del pie Bader', copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        if any(STOREFRONT_FIELDS.intersection(vals) for vals in vals_list):
            self._bpi_check_storefront_admin()
        return super().create(vals_list)

    def write(self, vals):
        if STOREFRONT_FIELDS.intersection(vals):
            self._bpi_check_storefront_admin()
        return super().write(vals)

    def _bpi_check_storefront_admin(self):
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Solo los administradores pueden editar el diseño Bader del sitio.'))

    @api.constrains(*STOREFRONT_FIELDS)
    def _check_bpi_premium_footer(self):
        for website in self:
            if website.bpi_premium_storefront_enabled and (
                    not html2plaintext(website.bpi_premium_footer_html or '').strip()
                    or not (website.bpi_premium_footer_legal_name or '').strip()):
                raise ValidationError(_(
                    'Prepara el contenido y la razón social del pie Bader de este sitio antes de activar el diseño.'))

    def _bpi_storefront_year(self):
        return fields.Date.today().year


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    bpi_premium_storefront_enabled = fields.Boolean(
        related='website_id.bpi_premium_storefront_enabled', readonly=False)
    bpi_premium_footer_html = fields.Html(
        related='website_id.bpi_premium_footer_html', readonly=False)
    bpi_premium_footer_legal_name = fields.Char(
        related='website_id.bpi_premium_footer_legal_name', readonly=False)
