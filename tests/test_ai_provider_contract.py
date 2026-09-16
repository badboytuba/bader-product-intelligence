# -*- coding: utf-8 -*-
"""Provider boundaries: malformed external data is never an Odoo traceback.

All transports are mocked. These tests do not need credentials, perform paid
requests or change the configured provider models.
"""
import json
from unittest.mock import Mock, patch

import requests

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from ..models import product_intelligence as provider


@tagged("-at_install", "post_install")
class TestBPIAIProviderContract(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env["bpi.service"]

    def _response(self, payload, status=200):
        response = Mock(status_code=status)
        response.json.return_value = payload
        if status >= 400:
            response.raise_for_status.side_effect = requests.HTTPError(response=response)
        return response

    def test_json_action_requires_object_not_any_valid_json(self):
        for value in ([], ["text"], None, True, False, 1, "text"):
            with self.subTest(value=value), \
                    patch.object(type(self.service), "_openai_response", return_value=json.dumps(value)):
                with self.assertRaises(UserError):
                    self.service._openai_json("JSON proposal")

    def test_json_object_and_fenced_object_preserve_existing_contract(self):
        for text in ('{"description": "Propuesta"}', '```json\n{"description": "Propuesta"}\n```'):
            with self.subTest(text=text), \
                    patch.object(type(self.service), "_openai_response", return_value=text):
                self.assertEqual(self.service._openai_json("JSON proposal"), {"description": "Propuesta"})

    def test_json_invalid_or_nontext_output_is_safe(self):
        for value in ("", "{bad JSON", [], {}, 42, True):
            with self.subTest(value=value), \
                    patch.object(type(self.service), "_openai_response", return_value=value):
                with self.assertRaises(UserError):
                    self.service._openai_json("JSON proposal")

    def test_text_response_accepts_direct_and_nested_output(self):
        self.assertEqual(self.service._parse_openai_text({"output_text": "  Proposal  "}), "Proposal")
        payload = {"status": "completed", "output": [
            {"type": "reasoning", "summary": []},
            {"type": "message", "content": [
                {"type": "output_text", "text": "First"},
                {"type": "output_text", "text": "Second"},
            ]},
        ]}
        self.assertEqual(self.service._parse_openai_text(payload), "First\nSecond")

    def test_text_response_rejects_malformed_envelope_and_parts(self):
        payloads = [
            [], None, "body", 42,
            {"output_text": ["text"]},
            {"output": {"type": "message"}},
            {"output": ["message"]},
            {"output": [{"type": "message", "content": "text"}]},
            {"output": [{"type": "message", "content": ["text"]}]},
            {"output": [{"type": "message", "content": [{"type": "output_text", "text": []}]}]},
            {"output": [{"type": "message", "content": [{"type": "output_text", "text": None}]}]},
        ]
        for payload in payloads:
            with self.subTest(payload=payload), self.assertRaises(UserError):
                self.service._parse_openai_text(payload)

    def test_incomplete_or_failed_response_never_becomes_a_complete_proposal(self):
        for state in ("failed", "incomplete", "cancelled", "queued", "in_progress"):
            with self.subTest(state=state), self.assertRaises(UserError):
                self.service._parse_openai_text({"status": state, "output_text": '{"description":"Partial"}'})
        with self.assertRaises(UserError) as error:
            self.service._parse_openai_text({"error": {"message": "PRIVATE_PROVIDER_DETAIL"}})
        self.assertNotIn("PRIVATE_PROVIDER_DETAIL", str(error.exception))

    def test_http_success_requires_object_envelope_and_no_error(self):
        for payload in ([], ["body"], "body", None, 42, {"error": "PRIVATE_PROVIDER_DETAIL"}):
            with self.subTest(payload=payload), \
                    patch.object(type(self.service), "_openai_headers", return_value={}), \
                    patch.object(provider.requests, "post", return_value=self._response(payload)) as transport, \
                    self.assertRaises(UserError) as error:
                self.service._openai_request("responses", json_payload={})
            self.assertEqual(transport.call_count, 1)
            self.assertNotIn("PRIVATE_PROVIDER_DETAIL", str(error.exception))

    def test_http_malformed_error_envelope_keeps_safe_error_classification(self):
        payloads = [[], "PRIVATE_PROVIDER_DETAIL", None, {"error": []},
                    {"error": "PRIVATE_PROVIDER_DETAIL"}, {"error": {"code": ["bad"]}}]
        for status in (400, 401, 403, 404):
            for payload in payloads:
                with self.subTest(status=status, payload=payload), \
                        patch.object(type(self.service), "_openai_headers", return_value={}), \
                        patch.object(provider.requests, "post", return_value=self._response(payload, status)) as transport, \
                        self.assertRaises(UserError) as error:
                    self.service._openai_request("responses", json_payload={})
                self.assertEqual(transport.call_count, 1)
                self.assertNotIn("PRIVATE_PROVIDER_DETAIL", str(error.exception))

    def test_billing_failure_and_timeout_never_replay_a_paid_request(self):
        for code in ("billing_not_active", "insufficient_quota", "quota_exceeded"):
            response = self._response({"error": {"code": code, "message": "PRIVATE_PROVIDER_DETAIL"}}, 429)
            with self.subTest(code=code), \
                    patch.object(type(self.service), "_openai_headers", return_value={}), \
                    patch.object(provider.requests, "post", return_value=response) as transport, \
                    self.assertRaises(UserError) as error:
                self.service._openai_request("responses", json_payload={})
            self.assertEqual(transport.call_count, 1)
            self.assertNotIn("PRIVATE_PROVIDER_DETAIL", str(error.exception))
        with patch.object(type(self.service), "_openai_headers", return_value={}), \
                patch.object(provider.requests, "post", side_effect=requests.Timeout("PRIVATE_PROVIDER_DETAIL")) as transport, \
                self.assertRaises(UserError) as error:
            self.service._openai_request("images/generations", json_payload={})
        self.assertEqual(transport.call_count, 1)
        self.assertNotIn("PRIVATE_PROVIDER_DETAIL", str(error.exception))

    def test_http_non_json_error_is_safe_and_does_not_retry(self):
        for status in (200, 400):
            response = self._response(None, status)
            response.json.side_effect = ValueError("PRIVATE_PROVIDER_DETAIL")
            with self.subTest(status=status), \
                    patch.object(type(self.service), "_openai_headers", return_value={}), \
                    patch.object(provider.requests, "post", return_value=response) as transport, \
                    self.assertRaises(UserError) as error:
                self.service._openai_request("responses", json_payload={})
            self.assertEqual(transport.call_count, 1)
            self.assertNotIn("PRIVATE_PROVIDER_DETAIL", str(error.exception))

    def test_missing_key_is_checked_before_transport(self):
        with patch.object(type(self.service), "_get_config", return_value=False), \
                patch.object(provider.requests, "post", side_effect=AssertionError("Credentials are missing")) as transport, \
                self.assertRaises(UserError):
            self.service._openai_request("responses", json_payload={})
        transport.assert_not_called()

    def test_image_response_accepts_both_existing_envelopes(self):
        expected = {"mimeType": "image/png", "data": "aW1hZ2U="}
        self.assertEqual(self.service._extract_openai_image({"data": [{"b64_json": "aW1hZ2U="}]}), expected)
        self.assertEqual(self.service._extract_openai_image({"output": [
            {"type": "image_generation_call", "result": "aW1hZ2U="},
        ]}), expected)

    def test_image_response_rejects_nonobject_nonlist_and_nontext_data(self):
        payloads = [[], None, "body", 42, {"data": "body"}, {"data": ["body"]},
                    {"data": [{"b64_json": ["body"]}]}, {"output": "body"},
                    {"output": ["body"]}, {"output": [{"type": "image_generation_call", "result": ["body"]}]}]
        for payload in payloads:
            with self.subTest(payload=payload), self.assertRaises(UserError):
                self.service._extract_openai_image(payload)

    def test_content_and_category_invalid_json_fail_before_any_product_write(self):
        product = self.env["product.template"].create({"name": "BPI provider contract", "description_sale": "Saved content"})
        with patch.object(type(self.service), "_openai_response", return_value="[]"), \
                patch.object(type(product), "write", side_effect=AssertionError("Invalid proposal cannot be saved")):
            for method in (self.service.generate_content, self.service.generate_faq):
                with self.subTest(method=method.__name__), self.assertRaises(UserError):
                    method(product)

    def test_classification_invalid_json_fails_before_product_write(self):
        product = self.env['product.template'].create({'name': 'Classifier contract'})
        with patch.object(type(self.service), '_openai_json', return_value=[]), patch.object(type(product), 'write', side_effect=AssertionError('No proposal write')):
            with self.assertRaises(UserError):
                self.service._classification_proposal(product, {}, [])
