# Copyright 2026 Bader Business
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import json
from unittest.mock import Mock, patch

import requests

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import SavepointCase, new_test_user


class TestCompetitorMetadata(SavepointCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env["bpi.service"]
        cls.product = cls.env["product.template"].create({"name": "Competitor parser specimen", "list_price": 20})
        cls.competitor = cls.env["bpi.product.competitor"].create({
            "product_tmpl_id": cls.product.id, "competitor_name": "Public product",
            "competitor_url": "https://example.com/product", "competitor_currency": "ARS"})

    def _html(self, keywords=True, price=33000):
        return """<html><head><title>Dental &amp; Salud — Clamp</title>
            <meta data-x="1" content="Descripción &amp; detalles del clamp" name="description">
            %s
            <meta data-x="1" property="og:description" content="Open Graph only">
            <link href="/product" data-x="1" rel="canonical">
            <script id="product-schema" type="application/ld+json">%s</script>
            </head><body><h1>Clamp <em>dental</em> &amp; acero</h1>
            <h2>Características</h2><h2>Uso clínico</h2>
            <p>Descripción comercial visible del producto para aislamiento dental.</p></body></html>""" % (
                '<meta data-y="2" name="keywords" content="clamp, aislamiento, acero">' if keywords else "",
                json.dumps({"@type": "Product", "url": self.competitor.competitor_url,
                            "offers": {"@type": "Offer", "price": price, "priceCurrency": "ARS"}}))

    def _apply(self, html=None, **values):
        data = {"html": self._html() if html is None else html, "metadata": {"statusCode": 200}}
        data.update(values)
        with patch.object(type(self.service), "_validate_external_url", side_effect=lambda value: value):
            return self.service._apply_competitor_scrape_data(self.competitor, data, source="direct_http")

    def _response(self, body, status=200, content_type="text/html", location=None):
        response = Mock()
        response.status_code = status
        response.headers = {"Content-Type": content_type}
        if location:
            response.headers["Location"] = location
        response.encoding = "utf-8"
        response.iter_content.return_value = [body.encode() if isinstance(body, str) else body]
        return response

    def _configuration(self, key, default=None):
        return {"bader_product_intelligence.firecrawl_api_key": "test-only-key",
                "bader_product_intelligence.firecrawl_base_url": "https://api.firecrawl.dev"}.get(key, default)

    def test_html_metadata_is_attribute_order_independent_and_entity_decoded(self):
        result = self._apply()
        self.assertEqual(result["metaTitle"], "Dental & Salud — Clamp")
        self.assertEqual(result["metaDescription"], "Descripción & detalles del clamp")
        self.assertEqual(result["metaKeywords"], ["clamp", "aislamiento", "acero"])
        self.assertEqual(result["metaKeywordsSource"], "page")
        self.assertEqual(result["h1Tags"], ["Clamp dental & acero"])
        self.assertEqual(result["h2Tags"], ["Características", "Uso clínico"])
        self.assertEqual(result["canonicalUrl"], "https://example.com/product")
        self.assertTrue(result["lastSuccessfulScrapedAt"])

    def test_jsonld_id_before_type_and_graph_are_collected(self):
        data = self.service._extract_structured_data(self._html())
        self.assertEqual(data[0]["@type"], "Product")
        result = self._apply()
        self.assertEqual(result["competitorPrice"], 33000)
        self.assertEqual(result["priceSource"], "jsonld_offer")
        self.assertEqual(result["priceStatus"], "known")

    def test_raw_html_precedes_cleaned_html_for_source_metadata_and_schema(self):
        result = self._apply(
            '<html><body><h1>Cleaned product heading</h1><p>Visible body only.</p></body></html>',
            rawHtml=self._html(), markdown="Visible body only.",
            metadata={"statusCode": 200, "title": "Provider fallback title"})
        self.assertEqual(result["metaTitle"], "Dental & Salud — Clamp")
        self.assertEqual(result["metaDescription"], "Descripción & detalles del clamp")
        self.assertEqual(result["metaKeywords"], ["clamp", "aislamiento", "acero"])
        self.assertEqual(result["metaKeywordsSource"], "page")
        self.assertEqual(result["h1Tags"], ["Clamp dental & acero"])
        self.assertEqual(result["canonicalUrl"], "https://example.com/product")
        self.assertEqual(result["competitorPrice"], 33000)
        self.assertEqual(result["priceSource"], "jsonld_offer")
        self.assertEqual(result["priceStatus"], "known")

    def test_missing_meta_keywords_are_not_invented_from_old_or_page_content(self):
        self.competitor.write({"competitor_description": "Invented old keyword", "meta_keywords": ["old keyword"]})
        result = self._apply(self._html(keywords=False))
        self.assertEqual(result["metaKeywords"], [])
        self.assertEqual(result["metaKeywordsSource"], "not_found")

    def test_legacy_keywords_have_unknown_origin_until_successful_refresh(self):
        self.competitor.write({"meta_keywords": ["legacy derived phrase"]})
        self.assertEqual(self.competitor.bpi_to_payload()["metaKeywordsSource"], "legacy_unknown")

    def test_og_metadata_does_not_masquerade_as_seo_title_description(self):
        result = self._apply('<html><head><meta property="og:title" content="Social title"><meta property="og:description" content="Social description"></head><body><h1>Page heading</h1></body></html>')
        self.assertEqual(result["metaTitle"], "")
        self.assertEqual(result["metaDescription"], "")
        self.assertEqual(result["ogTitle"], "Social title")
        self.assertEqual(result["ogDescription"], "Social description")

    def test_visible_us_dollar_symbol_is_usd_not_ars(self):
        for text in ("US$ 20.00", "USD 20.00", "U$S 20,00", "Precio: US$ 20.00."):
            price, offer, currency = self.service._extract_prices("", text, [])
            self.assertEqual((price, offer, currency), (20, False, "USD"), text)

    def test_locale_price_and_sentence_punctuation_do_not_multiply_amount(self):
        for raw, expected in (("1.750,50", 1750.5), ("1,750.50", 1750.5), ("100.00.", 100), ("25 000,00", 25000)):
            self.assertEqual(self.service._parse_price_number(raw), expected)

    def test_nonfinite_negative_and_merged_numbers_are_rejected(self):
        for raw in (float("inf"), float("nan"), -1, "-10.00", "3 cuotas 100", True):
            self.assertFalse(self.service._parse_price_number(raw), raw)
        for raw in (float("inf"), float("nan")):
            self.assertFalse(self.service._competitor_price_to_usd(raw, "USD", 1650))

    def test_shipping_installments_and_ranges_are_not_fake_discounts(self):
        for text in ("Precio $ 100.00. Envío $ 20.00.", "3 cuotas de $ 100", "Desde $ 100 hasta $ 200"):
            evidence = self.service._extract_competitor_price_evidence("", text, [])
            self.assertFalse(evidence["price"])
            self.assertFalse(evidence["offerPrice"])
        price, offer, currency = self.service._extract_prices("", "Precio: $100\nEnvío: $20", [])
        self.assertEqual((price, offer, currency), (100, False, "ARS"))

    def test_aggregate_offer_range_is_ambiguous_not_discount(self):
        data = [{"@type": "AggregateOffer", "lowPrice": 80, "highPrice": 120, "priceCurrency": "USD"}]
        evidence = self.service._extract_competitor_price_evidence("", "", data)
        self.assertEqual(evidence["status"], "ambiguous")
        self.assertFalse(evidence["price"])
        self.assertFalse(evidence["offerPrice"])

    def test_different_currencies_never_cross_contaminate_amounts(self):
        data = [{"@type": "Product", "offers": [
            {"@type": "Offer", "price": 100, "priceCurrency": "USD"},
            {"@type": "Offer", "price": 5000, "priceCurrency": "ARS"}]}]
        evidence = self.service._extract_competitor_price_evidence("", "", data)
        self.assertEqual(evidence["status"], "ambiguous")
        self.assertFalse(evidence["price"])

    def test_malformed_jsonld_offer_id_is_ignored_without_type_error(self):
        for value in ([], {}, ["https://example.com/offer"]):
            data = [{"@type": "Product", "offers": {"@id": value}}]
            evidence = self.service._extract_competitor_price_evidence("", "", data)
            self.assertFalse(evidence["price"])
            self.assertEqual(evidence["status"], "not_found")

    def test_only_product_matching_page_is_selected_not_related_lowest_price(self):
        data = [{"@graph": [
            {"@type": "Product", "url": "https://example.com/product", "offers": {"price": 100, "priceCurrency": "USD"}},
            {"@type": "Product", "url": "https://example.com/related", "offers": {"price": 1, "priceCurrency": "ARS"}}]}]
        evidence = self.service._extract_competitor_price_evidence("", "", data, source_url=self.competitor.competitor_url)
        self.assertEqual((evidence["price"], evidence["currency"]), (100, "USD"))
        self.assertEqual(self.service._extract_competitor_price_evidence("", "", data)["status"], "ambiguous")

    def test_product_price_meta_tags_are_a_supported_explicit_source(self):
        html = '<meta content="99.99" itemprop="price"><meta itemprop="priceCurrency" content="USD">'
        evidence = self.service._extract_competitor_price_evidence(html, "", [])
        self.assertEqual((evidence["price"], evidence["currency"], evidence["source"]), (99.99, "USD", "product_meta"))

    def test_successful_page_without_price_has_explicit_unknown_not_old_price(self):
        self._apply()
        result = self._apply("<html><title>Page without price</title><body><h1>New page content</h1></body></html>")
        self.assertFalse(result["competitorPrice"])
        self.assertFalse(result["competitorOfferPrice"])
        self.assertEqual(result["priceStatus"], "not_found")
        self.assertFalse(result["priceComparisonAvailable"])

    def test_empty_malformed_blocked_and_provider_failed_payloads_do_not_erase_snapshot(self):
        before = self._apply()
        for data in ({}, {"success": False}, {"html": []}, {"html": "<html></html>"},
                     {"html": self._html(), "metadata": {"statusCode": 403}},
                     {"html": "<title>Just a moment...</title><body>Captcha</body>"}):
            with patch.object(type(self.service), "_validate_external_url", side_effect=lambda value: value):
                with self.assertRaises(UserError):
                    self.service._apply_competitor_scrape_data(self.competitor, data)
        self.assertEqual(self.competitor.meta_title, before["metaTitle"])
        self.assertEqual(self.competitor.competitor_price, before["competitorPrice"])

    def test_failed_refresh_returns_persistable_failure_and_preserves_last_valid_fields(self):
        before = self._apply()
        with patch.object(type(self.service), "_get_config", return_value=False), \
             patch.object(type(self.service), "_validate_external_url", side_effect=lambda value: value), \
             patch.object(type(self.service), "_fetch_competitor_direct", side_effect=UserError("Consulta bloqueada")):
            result = self.service.scrape_competitor(self.competitor)
        self.assertEqual(result["scrapeStatus"], "failed")
        self.assertEqual(self.competitor.scrape_status, "failed")
        for key in ("metaTitle", "metaDescription", "metaKeywords", "metaKeywordsSource", "competitorPrice", "priceStatus", "priceSource", "lastSuccessfulScrapedAt"):
            self.assertEqual(result[key], before[key], key)
        self.assertEqual(result["scrapeError"], "Consulta bloqueada")

    def test_firecrawl_requests_unfiltered_content_and_validates_result(self):
        response = self._response(json.dumps({"success": True, "data": {"html": self._html(), "metadata": {"statusCode": 200}}}), content_type="application/json")
        with patch.object(type(self.service), "_get_config", side_effect=self._configuration), \
             patch.object(type(self.service), "_validate_external_url", side_effect=lambda value: value), \
             patch("odoo.addons.bader_product_intelligence.models.product_intelligence.requests.post", return_value=response) as post, \
             patch.object(type(self.service), "_fetch_competitor_direct", side_effect=AssertionError("No fallback needed")):
            result = self.service.scrape_competitor(self.competitor)
        self.assertEqual(result["scrapeSource"], "firecrawl")
        self.assertNotIn("includeTags", post.call_args.kwargs["json"])
        self.assertFalse(post.call_args.kwargs["allow_redirects"])
        self.assertTrue(post.call_args.kwargs["stream"])
        response.close.assert_called_once()

    def test_firecrawl_v1_requests_raw_html_and_accepts_raw_only_response(self):
        response = self._response(json.dumps({"success": True, "data": {
            "rawHtml": self._html(), "markdown": "Visible product content.",
            "metadata": {"statusCode": 200}}}), content_type="application/json")
        with patch.object(type(self.service), "_get_config", side_effect=self._configuration), \
             patch.object(type(self.service), "_validate_external_url", side_effect=lambda value: value), \
             patch("odoo.addons.bader_product_intelligence.models.product_intelligence.requests.post", return_value=response) as post, \
             patch.object(type(self.service), "_fetch_competitor_direct", side_effect=AssertionError("No fallback needed")):
            result = self.service.scrape_competitor(self.competitor)
        self.assertTrue(post.call_args.args[0].endswith("/v1/scrape"))
        self.assertEqual(post.call_args.kwargs["json"]["formats"], ["markdown", "rawHtml"])
        self.assertFalse(post.call_args.kwargs["json"]["onlyMainContent"])
        self.assertEqual(result["scrapeSource"], "firecrawl")
        self.assertEqual(result["metaKeywordsSource"], "page")
        self.assertEqual(result["competitorPrice"], 33000)
        self.assertEqual(result["priceSource"], "jsonld_offer")
        response.close.assert_called_once()

    def test_firecrawl_http200_failure_falls_back_without_clearing_valid_metadata(self):
        response = self._response(json.dumps({"success": False, "error": "provider-secret-body"}), content_type="application/json")
        with patch.object(type(self.service), "_get_config", side_effect=self._configuration), \
             patch.object(type(self.service), "_validate_external_url", side_effect=lambda value: value), \
             patch("odoo.addons.bader_product_intelligence.models.product_intelligence.requests.post", return_value=response), \
             patch.object(type(self.service), "_fetch_competitor_direct", return_value={"html": self._html(), "metadata": {"statusCode": 200}}):
            result = self.service.scrape_competitor(self.competitor)
        self.assertEqual(result["scrapeStatus"], "success")
        self.assertEqual(result["scrapeSource"], "direct_http")
        self.assertNotIn("provider-secret-body", str(result))

    def test_direct_http_stream_is_bounded_and_redirects_closed(self):
        redirect = self._response("", status=302, location="/final")
        final = self._response(self._html())
        with patch.object(type(self.service), "_validate_external_url", side_effect=lambda value: value), \
             patch("odoo.addons.bader_product_intelligence.models.product_intelligence.requests.get", side_effect=[redirect, final]) as get:
            data = self.service._fetch_competitor_direct(self.competitor.competitor_url)
        self.assertEqual(data["sourceURL"], "https://example.com/final")
        self.assertTrue(get.call_args.kwargs["stream"])
        self.assertFalse(get.call_args.kwargs["allow_redirects"])
        redirect.close.assert_called_once()
        final.close.assert_called_once()

    def test_direct_http_rejects_oversized_mime_and_redirect_exhaustion(self):
        oversized = self._response(b"x" * 2500001)
        bad_mime = self._response(b"%PDF-1", content_type="application/pdf")
        for response in (oversized, bad_mime):
            with patch.object(type(self.service), "_validate_external_url", side_effect=lambda value: value), \
                 patch("odoo.addons.bader_product_intelligence.models.product_intelligence.requests.get", return_value=response):
                with self.assertRaises(UserError):
                    self.service._fetch_competitor_direct(self.competitor.competitor_url)
            response.close.assert_called_once()
        response = self._response("", status=302, location="/again")
        with patch.object(type(self.service), "_validate_external_url", side_effect=lambda value: value), \
             patch("odoo.addons.bader_product_intelligence.models.product_intelligence.requests.get", return_value=response) as get:
            with self.assertRaises(UserError):
                self.service._fetch_competitor_direct(self.competitor.competitor_url)
        self.assertEqual(get.call_count, 6)

    def test_redirect_to_private_address_is_denied_before_second_request(self):
        response = self._response("", status=302, location="http://127.0.0.1/private")
        def resolve(host, *args, **kwargs):
            return [(2, 1, 6, "", ("127.0.0.1" if host == "127.0.0.1" else "93.184.216.34", 80))]
        with patch("odoo.addons.bader_product_intelligence.models.product_intelligence.socket.getaddrinfo", side_effect=resolve), \
             patch("odoo.addons.bader_product_intelligence.models.product_intelligence.requests.get", return_value=response) as get:
            with self.assertRaises(UserError):
                self.service._fetch_competitor_direct(self.competitor.competitor_url)
        self.assertEqual(get.call_count, 1)

    def test_unsafe_metadata_urls_and_credentials_are_not_exposed(self):
        for url in ("http://127.0.0.1/x", "http://[::1]/x", "javascript:alert(1)", "https://user:pass@example.com/x", "https://example.com:8080/x"):
            self.assertEqual(self.service._competitor_public_metadata_url(url, self.competitor.competitor_url), "")
        with self.assertRaises(UserError):
            self.service._competitor_safe_url("https://user:pass@example.com/x")

    def test_ai_suggestions_are_separate_and_do_not_overwrite_observed_page_metadata(self):
        before = self._apply()
        with patch.object(type(self.service), "_openai_json", return_value={
            "competitorTitle": "Invented title", "competitorDescription": "Invented description",
            "competitorFeatures": ["Invented feature"], "priceComparison": "invalid-choice",
            "recommendedKeywords": ["keyword recommendation"], "contentStrategy": "Improve helpful details",
            "strengthsVsUs": ["Clear structure"], "weaknessesVsUs": ["Limited specifications"]}):
            result = self.service.analyze_competitor(self.competitor)
        self.assertEqual(result["metaTitle"], before["metaTitle"])
        self.assertEqual(result["competitorTitle"], before["competitorTitle"])
        self.assertEqual(result["competitorDescription"], before["competitorDescription"])
        self.assertEqual(result["metaKeywords"], before["metaKeywords"])
        self.assertEqual(result["recommendedKeywords"], ["keyword recommendation"])
        self.assertEqual(result["contentStrategy"], "Improve helpful details")
        self.assertTrue(result["lastAnalyzedAt"])
        self.assertIn(result["priceComparison"], ("cheaper", "similar", "expensive"))

    def test_analysis_without_observed_content_never_calls_ai(self):
        with patch.object(type(self.service), "_openai_json", side_effect=AssertionError("No invented competitor analysis")):
            with self.assertRaises(UserError):
                self.service.analyze_competitor(self.competitor)

    def test_non_administrator_cannot_trigger_scrape_or_analysis(self):
        user = new_test_user(self.env, login="bpi_competitor_no_admin", groups="base.group_user")
        service = self.service.with_user(user)
        with patch("odoo.addons.bader_product_intelligence.models.product_intelligence.requests.get", side_effect=AssertionError("No requests")), \
             patch.object(type(self.service), "_openai_json", side_effect=AssertionError("No AI")):
            with self.assertRaises(AccessError):
                service.scrape_competitor(self.competitor.with_user(user))
            with self.assertRaises(AccessError):
                service.analyze_competitor(self.competitor.with_user(user))
