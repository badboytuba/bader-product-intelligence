# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    bpi_gemini_api_key = fields.Char(
        string="Gemini API Key",
        config_parameter="bader_product_intelligence.gemini_api_key",
    )
    bpi_gemini_text_model = fields.Char(
        string="Gemini Modelo Texto",
        default="gemini-2.5-flash",
        config_parameter="bader_product_intelligence.gemini_text_model",
    )
    bpi_gemini_image_model = fields.Char(
        string="Gemini Modelo Imagen",
        default="gemini-2.5-flash-image",
        config_parameter="bader_product_intelligence.gemini_image_model",
    )
    bpi_gemini_image_pro_model = fields.Char(
        string="Gemini Modelo Imagen Pro",
        default="gemini-2.5-flash-image",
        config_parameter="bader_product_intelligence.gemini_image_pro_model",
    )
    bpi_firecrawl_api_key = fields.Char(
        string="Firecrawl API Key",
        config_parameter="bader_product_intelligence.firecrawl_api_key",
    )
    bpi_firecrawl_base_url = fields.Char(
        string="Firecrawl Base URL",
        default="https://api.firecrawl.dev",
        config_parameter="bader_product_intelligence.firecrawl_base_url",
    )
    bpi_exchange_rate = fields.Integer(
        string="Tipo de Cambio ARS",
        default=1650,
        config_parameter="bader_product_intelligence.exchange_rate",
    )
