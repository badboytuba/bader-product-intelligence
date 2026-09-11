# -*- coding: utf-8 -*-
{
    "name": "Producto Intelligence",
    "version": "16.0.1.6.0",
    "summary": "Producto Intelligence para Bader en Odoo 16",
    "description": """
Producto Intelligence para Bader Argentina.

Replica dentro de Odoo las capacidades principales del módulo Product Intelligence:
- SEO/GEO con IA
- Galería e imágenes generadas con OpenAI
- Video de producto
- Descubrimiento y análisis de competidores
- Estrategia competitiva
- Agente IA por producto
- Inteligencia de categoría
    """,
    "author": "OpenAI Codex",
    "license": "LGPL-3",
    "category": "Website",
    "depends": [
        "product",
        "web",
        "website_sale",
        "product_pack",
        "sale_product_pack",
        "stock_product_pack",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ai_job_cron.xml",
        "views/product_views.xml",
        "views/category_views.xml",
        "views/res_config_settings_views.xml",
        "views/product_intelligence_action.xml",
        "views/website_product_templates.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "bader_product_intelligence/static/src/scss/product_intelligence.scss",
            "bader_product_intelligence/static/src/scss/dashboard.scss",
            "bader_product_intelligence/static/src/scss/catalog.scss",
            "bader_product_intelligence/static/src/scss/detail.scss",
            "bader_product_intelligence/static/src/js/product_intelligence_action.js",
            "bader_product_intelligence/static/src/xml/product_intelligence_templates.xml",
        ],
        "web.assets_qweb": [
            "bader_product_intelligence/static/src/xml/product_intelligence_templates.xml",
        ],
        "web.assets_frontend": [
            "bader_product_intelligence/static/src/scss/product_intelligence.scss",
            "bader_product_intelligence/static/src/scss/storefront_technical_description.scss",
            "bader_product_intelligence/static/src/scss/storefront_faq.scss",
        ],
        "web.qunit_suite_tests": [
            "bader_product_intelligence/static/tests/product_intelligence_tests.js",
        ],
    },
    "installable": True,
    "application": True,
}
