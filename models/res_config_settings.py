# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    bpi_openai_api_key = fields.Char(
        string="OpenAI API Key",
        config_parameter="bader_product_intelligence.openai_api_key",
    )
    bpi_openai_text_model = fields.Char(
        string="OpenAI Modelo Texto",
        default="gpt-5.5",
        config_parameter="bader_product_intelligence.openai_text_model",
    )
    bpi_openai_image_model = fields.Char(
        string="OpenAI Modelo Imagen",
        default="gpt-image-2",
        config_parameter="bader_product_intelligence.openai_image_model",
    )
    bpi_openai_image_edit_model = fields.Char(
        string="OpenAI Modelo Edición Imagen",
        default="gpt-image-1.5",
        config_parameter="bader_product_intelligence.openai_image_edit_model",
    )
    bpi_openai_reasoning_effort = fields.Selection(
        [
            ("none", "None"),
            ("minimal", "Minimal"),
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("xhigh", "XHigh"),
        ],
        string="OpenAI Reasoning Effort",
        default="low",
        config_parameter="bader_product_intelligence.openai_reasoning_effort",
    )
    bpi_openai_text_verbosity = fields.Selection(
        [
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
        ],
        string="OpenAI Verbosidad Texto",
        default="medium",
        config_parameter="bader_product_intelligence.openai_text_verbosity",
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
