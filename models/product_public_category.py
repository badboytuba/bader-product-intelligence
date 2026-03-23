# -*- coding: utf-8 -*-

from odoo import fields, models


class ProductPublicCategory(models.Model):
    _inherit = "product.public.category"

    bpi_local_name = fields.Char(string="Nombre Local")
    bpi_local_aliases = fields.Json(string="Alias Locales", default=list)
    bpi_target_audiences = fields.Json(string="Audiencias Objetivo", default=list)
    bpi_audience_descriptions = fields.Json(string="Descripciones por Audiencia", default=dict)
    bpi_seo_keywords = fields.Json(string="Keywords SEO", default=list)
    bpi_geo_keywords = fields.Json(string="Keywords GEO", default=list)
    bpi_meta_description = fields.Text(string="Meta Description")
    bpi_search_volume = fields.Char(string="Volumen de Búsqueda")
    bpi_competitiveness = fields.Char(string="Competitividad")
    bpi_trend_direction = fields.Selection(
        [
            ("up", "Subiendo"),
            ("stable", "Estable"),
            ("down", "Bajando"),
        ],
        string="Tendencia",
    )
    bpi_seasonality = fields.Char(string="Estacionalidad")
    bpi_last_analyzed_at = fields.Datetime(string="Último Análisis")

    def bpi_to_payload(self):
        self.ensure_one()
        descriptions = self.bpi_audience_descriptions or {}
        return {
            "id": self.id,
            "categoryName": self.name,
            "localName": self.bpi_local_name or "",
            "localAliases": self.bpi_local_aliases or [],
            "targetAudiences": self.bpi_target_audiences or [],
            "seoKeywords": self.bpi_seo_keywords or [],
            "geoKeywords": self.bpi_geo_keywords or [],
            "metaDescription": self.bpi_meta_description or "",
            "searchVolume": self.bpi_search_volume or "",
            "competitiveness": self.bpi_competitiveness or "",
            "trendDirection": self.bpi_trend_direction or "",
            "seasonality": self.bpi_seasonality or "",
            "clinicasDescription": descriptions.get("clinicas", ""),
            "laboratoriosDescription": descriptions.get("laboratorios", ""),
            "estudiantesDescription": descriptions.get("estudiantes", ""),
            "lastAnalyzedAt": self.bpi_last_analyzed_at.isoformat() if self.bpi_last_analyzed_at else False,
        }
