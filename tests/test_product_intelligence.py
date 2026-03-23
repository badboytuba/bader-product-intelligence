# -*- coding: utf-8 -*-

import socket
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("-at_install", "post_install")
class TestProductoIntelligence(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env["bpi.service"]
        cls.category = cls.env["product.public.category"].create({"name": "Fresas"})

        cls.product_published = cls.env["product.template"].create(
            {
                "name": "Producto Publicado",
                "default_code": "PUB-001",
                "list_price": 12.0,
                "standard_price": 5.0,
                "sale_ok": True,
                "website_published": True,
                "bpi_featured": True,
                "public_categ_ids": [(6, 0, [cls.category.id])],
            }
        )
        cls.product_new = cls.env["product.template"].create(
            {
                "name": "Producto Nuevo",
                "default_code": "NEW-001",
                "list_price": 20.0,
                "standard_price": 8.0,
                "sale_ok": True,
                "website_published": False,
                "public_categ_ids": [(6, 0, [cls.category.id])],
            }
        )
        cls.product_archived = cls.env["product.template"].create(
            {
                "name": "Producto Archivado",
                "default_code": "ARC-001",
                "list_price": 9.0,
                "sale_ok": True,
                "website_published": False,
            }
        )
        cls.product_archived.write({"active": False})

        cls.product_discontinued = cls.env["product.template"].create(
            {
                "name": "Producto Discontinuado",
                "default_code": "DIS-001",
                "list_price": 7.0,
                "sale_ok": False,
                "website_published": False,
            }
        )

    def test_dashboard_payload_is_paginated(self):
        payload = self.service.dashboard_payload(tab="all", search="", page=1, limit=1)

        self.assertEqual(payload["stats"]["total"], 4)
        self.assertEqual(payload["stats"]["published"], 1)
        self.assertEqual(payload["stats"]["featured"], 1)
        self.assertEqual(payload["tabCounts"]["all"], 2)
        self.assertEqual(payload["tabCounts"]["new"], 1)
        self.assertEqual(payload["tabCounts"]["discontinued"], 2)
        self.assertEqual(len(payload["products"]), 1)
        self.assertEqual(payload["pager"]["page"], 1)
        self.assertEqual(payload["pager"]["pageCount"], 2)
        self.assertTrue(payload["pager"]["hasNext"])
        self.assertFalse(payload["pager"]["hasPrevious"])

        search_payload = self.service.dashboard_payload(tab="all", search="NEW-001", page=1, limit=10)
        self.assertEqual(search_payload["pager"]["total"], 1)
        self.assertEqual(search_payload["products"][0]["sku"], "NEW-001")

    def test_update_product_generates_slug(self):
        payload = self.service.update_product(
            self.product_new,
            {
                "name": "Producto Inteligente Premium",
                "slug": "Producto Inteligente Premium!!",
                "featured": True,
            },
        )

        self.assertEqual(self.product_new.bpi_slug, "producto-inteligente-premium")
        self.assertTrue(self.product_new.bpi_featured)
        self.assertEqual(payload["product"]["slug"], "producto-inteligente-premium")

    def test_validate_external_url_blocks_private_networks(self):
        private_resolution = [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", 443)),
        ]
        public_resolution = [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", 443)),
        ]

        with patch(
            "odoo.addons.bader_product_intelligence.models.product_intelligence.socket.getaddrinfo",
            return_value=private_resolution,
        ):
            with self.assertRaises(UserError):
                self.service._validate_external_url("https://127.0.0.1/private.png")

        with patch(
            "odoo.addons.bader_product_intelligence.models.product_intelligence.socket.getaddrinfo",
            return_value=public_resolution,
        ):
            result = self.service._validate_external_url("https://example.com/image.png")

        self.assertEqual(result, "https://example.com/image.png")
