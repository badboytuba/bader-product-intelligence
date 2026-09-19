# -*- coding: utf-8 -*-
{
    "name": "Producto Intelligence",
    "version": "16.0.1.13.1",
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
        "bader_brand",
        "product",
        "web",
        "website_sale",
        "product_pack",
        "sale_product_pack",
        "stock_product_pack",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/technical_specification_rules.xml",
        "security/product_document_rules.xml",
        "security/content_studio_rules.xml",
        "data/ai_job_cron.xml",
        "data/description_media_cron.xml",
        "data/content_template_data.xml",
        "data/taxonomy_data.xml",
        "views/product_views.xml",
        "views/category_views.xml",
        "views/res_config_settings_views.xml",
        "views/product_intelligence_action.xml",
        "views/content_template_views.xml",
        "views/description_layout_templates.xml",
        "views/website_product_templates.xml",
        "views/taxonomy_views.xml",
        "views/taxonomy_website.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "bader_product_intelligence/static/src/scss/product_intelligence.scss",
            "bader_product_intelligence/static/src/scss/product_documents.scss",
            "bader_product_intelligence/static/src/scss/taxonomy.scss",
            "bader_product_intelligence/static/src/scss/taxonomy_prime.scss",
            "bader_product_intelligence/static/src/scss/semantic_map.scss",
            "bader_product_intelligence/static/src/scss/dashboard.scss",
            "bader_product_intelligence/static/src/scss/catalog.scss",
            "bader_product_intelligence/static/src/scss/detail.scss",
            "bader_product_intelligence/static/src/scss/content_studio.scss",
            "bader_product_intelligence/static/src/scss/description_layout.scss",
            "bader_product_intelligence/static/src/js/content_studio.js",
            "bader_product_intelligence/static/src/js/product_intelligence_action.js",
            "bader_product_intelligence/static/src/xml/product_intelligence_templates.xml",
            "bader_product_intelligence/static/src/xml/content_studio.xml",
        ],
        "web.assets_qweb": [
            "bader_product_intelligence/static/src/xml/product_intelligence_templates.xml",
            "bader_product_intelligence/static/src/xml/content_studio.xml",
        ],
        "web.assets_frontend": [
            "bader_product_intelligence/static/src/js/taxonomy_header.js",
            "bader_product_intelligence/static/src/scss/taxonomy_header.scss",
            "bader_product_intelligence/static/src/scss/product_intelligence.scss",
            "bader_product_intelligence/static/src/scss/product_documents.scss",
            "bader_product_intelligence/static/src/scss/taxonomy.scss",
            "bader_product_intelligence/static/src/scss/storefront_technical_description.scss",
            "bader_product_intelligence/static/src/scss/storefront_faq.scss",
            "bader_product_intelligence/static/src/scss/description_layout.scss",
            "bader_product_intelligence/static/src/js/description_layout_public.js",
        ],
        "web.qunit_suite_tests": [
            "bader_product_intelligence/static/tests/product_intelligence_tests.js",
            "bader_product_intelligence/static/tests/content_studio_tests.js",
        ],
    },
    "installable": True,
    "application": True,
}
