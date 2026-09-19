# -*- coding: utf-8 -*-
"""Offline transport tests: no external or local network connections."""
import importlib.util
import io
from email.message import Message
from pathlib import Path
import socket
import time
import unittest
from unittest.mock import MagicMock, patch

try:
    from odoo.tests.common import BaseCase, tagged
except ModuleNotFoundError:  # Pure transport suite is also usable off-server.
    BaseCase = unittest.TestCase

    def tagged(*_tags):
        return lambda cls: cls

try:
    from ..models import studio_fetch as fetch
except ImportError:  # Also executable without an Odoo runtime.
    spec = importlib.util.spec_from_file_location('bpi_studio_fetch_test_module', Path(__file__).resolve().parents[1] / 'models' / 'studio_fetch.py')
    fetch = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fetch)


def dns(address='93.184.216.34'):
    return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, '', (address, 443))]


class Response:
    def __init__(self, body=b'<p>Informacion confirmada</p>', status=200, headers=None):
        self.body = io.BytesIO(body)
        self.status = status
        self.headers = Message()
        for key, value in (headers or {'Content-Type': 'text/html; charset=utf-8'}).items():
            self.headers[key] = value
        self.closed = False

    def getheader(self, name):
        return self.headers.get(name)

    def read1(self, size):
        return self.body.read(size)

    def close(self):
        self.closed = True


@tagged('-at_install', 'post_install')
class TestStudioPinnedFetch(BaseCase):
    def target(self, url):
        return fetch._public_target(url, time.monotonic() + 35)

    def test_rejects_every_non_global_address_before_connection(self):
        for address in ('127.0.0.1', '10.0.0.1', '169.254.169.254', '100.64.0.1', '192.168.1.1', '0.0.0.0'):
            with self.subTest(address=address), patch.object(fetch.socket, 'getaddrinfo', return_value=dns(address)), patch.object(fetch, '_PinnedConnection') as connection:
                with self.assertRaises(fetch.PublicFetchError): fetch.fetch_public_page('https://source.example/product')
                connection.assert_not_called()

    def test_mixed_public_private_dns_answer_is_rejected(self):
        with patch.object(fetch.socket, 'getaddrinfo', return_value=dns() + dns('10.0.0.1')):
            with self.assertRaises(fetch.PublicFetchError): self.target('https://source.example/product')

    def test_rejects_credentials_controls_schemes_and_private_ports(self):
        for url in ('file:///etc/passwd', 'http://user:pass@source.example/a', 'https://source.example:444/a',
                    'https://source.example/\r\nHost:evil', 'https://source.example\\@127.0.0.1/a',
                    'http://localhost/', 'http://service.internal/a', 'http://[::1]/', 'http://100.64.0.1/',
                    'https://[2606:4700:4700::1111%25eth0]/'):
            with self.subTest(url=url), patch.object(fetch.socket, 'getaddrinfo') as resolver:
                with self.assertRaises(fetch.PublicFetchError): self.target(url)
                resolver.assert_not_called()

    def test_socket_connect_uses_validated_numeric_sockaddr(self):
        with patch.object(fetch.socket, 'getaddrinfo', return_value=dns()) as resolver:
            target = self.target('http://source.example/product')
        sock = MagicMock()
        # A later malicious DNS result is never consulted by connect().
        with patch.object(fetch.socket, 'socket', return_value=sock), patch.object(fetch.socket, 'getaddrinfo', side_effect=AssertionError('Second DNS lookup')):
            connection = fetch._PinnedConnection(target[1], target[2], target[3][0], False, time.monotonic() + 35)
            connection.connect()
            sock.connect.assert_called_once_with(('93.184.216.34', 443))
            connection.abort()
        self.assertEqual(resolver.call_count, 1)

    def test_https_keeps_original_hostname_for_tls_and_certificate(self):
        sock, wrapped, ssl_context = MagicMock(), MagicMock(), MagicMock()
        ssl_context.wrap_socket.return_value = wrapped
        with patch.object(fetch.socket, 'socket', return_value=sock), patch.object(fetch.ssl, 'create_default_context', return_value=ssl_context) as default_context:
            connection = fetch._PinnedConnection('original.example', 443, (socket.AF_INET, ('93.184.216.34', 443)), True, time.monotonic() + 35)
            connection.connect()
            default_context.assert_called_once_with()
            ssl_context.wrap_socket.assert_called_once_with(sock, server_hostname='original.example')
            self.assertIs(connection.sock, wrapped)
            connection.abort()

    def test_redirect_to_private_network_never_connects(self):
        response = Response(status=302, headers={'Location': 'http://127.0.0.1/private'})
        connection = MagicMock(); connection.getresponse.return_value = response
        with patch.object(fetch.socket, 'getaddrinfo', return_value=dns()), patch.object(fetch, '_PinnedConnection', return_value=connection) as create:
            with self.assertRaises(fetch.PublicFetchError): fetch.fetch_public_page('https://source.example/product')
        self.assertEqual(create.call_count, 1)
        self.assertTrue(response.closed)

    def test_same_hostname_redirect_resolves_again_and_rejects_rebinding(self):
        response = Response(status=302, headers={'Location': '/second'})
        connection = MagicMock(); connection.getresponse.return_value = response
        with patch.object(fetch.socket, 'getaddrinfo', side_effect=[dns(), dns('127.0.0.1')]) as resolver, patch.object(fetch, '_PinnedConnection', return_value=connection) as create:
            with self.assertRaises(fetch.PublicFetchError): fetch.fetch_public_page('https://source.example/product')
        self.assertEqual(resolver.call_count, 2)
        self.assertEqual(create.call_count, 1)

    def test_response_limits_compression_types_and_incomplete_length(self):
        cases = [
            Response(headers={'Content-Type': 'text/html', 'Content-Length': str(fetch.MAX_BYTES + 1)}),
            Response(headers={'Content-Type': 'text/html', 'Content-Encoding': 'gzip'}),
            Response(headers={'Content-Type': 'application/pdf'}),
            Response(body=b'a', headers={'Content-Type': 'text/plain', 'Content-Length': '10'}),
            Response(body=b'a' * 31, headers={'Content-Type': 'text/plain'}),
        ]
        for response in cases:
            connection = MagicMock(); connection.getresponse.return_value = response
            with self.subTest(headers=response.headers), patch.object(fetch, 'MAX_BYTES', 30), patch.object(fetch.socket, 'getaddrinfo', return_value=dns()), patch.object(fetch, '_PinnedConnection', return_value=connection):
                with self.assertRaises(fetch.PublicFetchError): fetch.fetch_public_page('https://source.example/product')
            self.assertTrue(response.closed)

    def test_success_uses_no_cookies_proxy_or_provider_and_returns_source(self):
        response = Response()
        connection = MagicMock(); connection.getresponse.return_value = response
        with patch.object(fetch.socket, 'getaddrinfo', return_value=dns()), patch.object(fetch, '_PinnedConnection', return_value=connection):
            data = fetch.fetch_public_page('https://source.example/product?ref=one#section')
        self.assertIn('Informacion', data['html'])
        self.assertEqual(data['sourceURL'], 'https://source.example/product?ref=one')
        args, kwargs = connection.request.call_args
        self.assertEqual(args, ('GET', '/product?ref=one'))
        self.assertEqual(kwargs['headers']['Host'], 'source.example')
        self.assertEqual(kwargs['headers']['Accept-Encoding'], 'identity')
        self.assertNotIn('Cookie', kwargs['headers'])


if __name__ == '__main__':
    unittest.main()
