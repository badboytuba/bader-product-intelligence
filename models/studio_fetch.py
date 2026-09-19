# -*- coding: utf-8 -*-
"""Bounded public-page transport exclusively for private Nancy source reads.

Resolve once per hop, reject every non-global result and connect to a numeric
validated sockaddr. Host routing, TLS SNI and certificate verification still use
the original hostname. No global resolver patch, proxy, cookie jar or importer.
"""
import http.client
import ipaddress
import queue
import re
import socket
import ssl
import threading
import time
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

MAX_BYTES = 2500000
TOTAL_SECONDS = 35


class PublicFetchError(ValueError):
    """Safe operator-facing error without credentials or response bodies."""


def _public_target(value, deadline):
    if not isinstance(value, str) or not value or len(value) > 2048 or re.search(r'[\x00-\x20\x7f\\]', value):
        raise PublicFetchError('Utiliza una dirección pública HTTP o HTTPS válida.')
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or '').encode('idna').decode('ascii').lower().rstrip('.')
        if parsed.scheme not in ('http', 'https') or not host or '%' in host or parsed.username or parsed.password or parsed.port not in (None, 80, 443):
            raise ValueError()
        port = parsed.port or (443 if parsed.scheme == 'https' else 80)
        if host == 'localhost' or host.endswith(('.localhost', '.local', '.internal', '.test', '.invalid')):
            raise ValueError()
        # Numeric hosts (including IPv6) are checked before any DNS operation.
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise ValueError()
    except (ValueError, UnicodeError):
        raise PublicFetchError('No se permiten credenciales, puertos privados ni direcciones internas.')

    answer = queue.Queue(maxsize=1)
    def resolve():
        try:
            answer.put(socket.getaddrinfo(host, port, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP))
        except (OSError, ValueError):
            answer.put(None)
    # Resolver can outlive a timeout, but cannot issue a commercial request;
    # daemon threads avoid blocking Odoo shutdown on a stalled OS resolver.
    threading.Thread(target=resolve, daemon=True, name='bpi-public-dns').start()
    remaining = min(5, deadline - time.monotonic())
    if remaining <= 0:
        raise PublicFetchError('La consulta superó el tiempo permitido.')
    try:
        entries = answer.get(timeout=remaining)
    except queue.Empty:
        raise PublicFetchError('No se pudo resolver el dominio dentro del tiempo permitido.')
    if not entries or len(entries) > 32:
        raise PublicFetchError('No se pudo resolver un destino público válido.')
    addresses = []
    for family, socktype, proto, _canonical, sockaddr in entries:
        try:
            address = ipaddress.ip_address(sockaddr[0])
            if not address.is_global or family not in (socket.AF_INET, socket.AF_INET6):
                raise ValueError()
            # Reject IPv4-mapped private IPv6 explicitly on Python versions
            # whose special-address classification differs.
            if getattr(address, 'ipv4_mapped', None) and not address.ipv4_mapped.is_global:
                raise ValueError()
        except (ValueError, TypeError):
            raise PublicFetchError('La dirección apunta a una red no pública y no está permitida.')
        if (family, sockaddr) not in addresses:
            addresses.append((family, sockaddr))
    host_header = '[%s]' % host if ':' in host else host
    if port != (443 if parsed.scheme == 'https' else 80):
        host_header += ':' + str(port)
    path = quote(parsed.path or '/', safe="/%:@!$&'()*+,;=-._~")
    query = quote(parsed.query, safe="/%?:@!$&'()*+,;=-._~")
    target = path + ('?' + query if query else '')
    canonical = urlunsplit((parsed.scheme, host_header, path, query, ''))
    return parsed.scheme, host, port, addresses, host_header, target, canonical


class _PinnedConnection(http.client.HTTPConnection):
    def __init__(self, host, port, address, tls, deadline):
        super().__init__(host, port=port, timeout=min(10, max(.1, deadline - time.monotonic())))
        self._address = address
        self._tls = tls
        self._deadline = deadline
        self._transport = None

    def connect(self):
        family, sockaddr = self._address
        transport = socket.socket(family, socket.SOCK_STREAM, socket.IPPROTO_TCP)
        self._transport = transport
        try:
            transport.settimeout(min(5, max(.1, self._deadline - time.monotonic())))
            transport.connect(sockaddr)  # Numeric sockaddr: never another DNS lookup.
            if self._tls:
                transport = ssl.create_default_context().wrap_socket(transport, server_hostname=self.host)
                self._transport = transport
            transport.settimeout(min(10, max(.1, self._deadline - time.monotonic())))
            self.sock = transport
        except BaseException:
            transport.close()
            raise

    def abort(self):
        transport = self._transport
        if transport:
            try:
                transport.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        self.close()


def fetch_public_page(url):
    return _fetch_public(url)


def fetch_public_image(url):
    """Private editor poster acquisition; same pinned transport and byte limits."""
    return _fetch_public(url, image=True)['body']


def _fetch_public(url, image=False):
    """GET at most six public resources, 2.5 MB identity body, 35 s total."""
    deadline = time.monotonic() + TOTAL_SECONDS
    current = url
    for hop in range(6):
        scheme, host, port, addresses, host_header, target, canonical = _public_target(current, deadline)
        if time.monotonic() >= deadline:
            raise PublicFetchError('La consulta superó el tiempo permitido.')
        # Fail closed rather than re-resolving or switching through an HTTP proxy.
        connection = _PinnedConnection(host, port, addresses[0], scheme == 'https', deadline)
        timer = threading.Timer(max(.1, deadline - time.monotonic()), connection.abort)
        timer.daemon = True
        timer.start()
        response = None
        try:
            connection.request('GET', target, headers={
                'Host': host_header, 'User-Agent': 'Bader-Nancy-SourceReader/1.0',
                'Accept': 'image/jpeg,image/png,image/webp' if image else 'text/html,application/xhtml+xml,text/plain',
                'Accept-Language': 'es-AR,es;q=0.9', 'Accept-Encoding': 'identity',
                'Connection': 'close',
            })
            response = connection.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                location = response.getheader('Location')
                if not location or hop == 5:
                    raise PublicFetchError('El enlace devuelve demasiadas redirecciones o un destino inválido.')
                current = urljoin(canonical, location)
                continue
            if not 200 <= response.status < 300:
                raise PublicFetchError('El sitio respondió HTTP %s. Puedes pegar la información pertinente como texto.' % response.status)
            content_type = (response.getheader('Content-Type') or '').lower().split(';', 1)[0].strip()
            if content_type not in (('image/jpeg', 'image/png', 'image/webp') if image else ('text/html', 'application/xhtml+xml', 'text/plain')):
                raise PublicFetchError('El enlace no devuelve una página de texto. Sube el documento directamente.')
            if (response.getheader('Content-Encoding') or 'identity').lower().strip() != 'identity':
                raise PublicFetchError('La página usa una compresión no admitida. Pega la información pertinente como texto.')
            length = response.getheader('Content-Length')
            if length is not None:
                try:
                    declared = int(length)
                except ValueError:
                    raise PublicFetchError('La página devuelve un tamaño no válido.')
                if declared < 0 or declared > MAX_BYTES:
                    raise PublicFetchError('La página supera el tamaño permitido.')
            parts, total = [], 0
            while True:
                if time.monotonic() >= deadline:
                    raise PublicFetchError('La consulta superó el tiempo permitido.')
                # read1 avoids waiting for 64 KB from a trickling peer. The
                # watchdog shutdown also bounds response/header slowloris.
                chunk = response.read1(min(65536, MAX_BYTES - total + 1))
                if time.monotonic() >= deadline:
                    raise PublicFetchError('La consulta superó el tiempo permitido.')
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_BYTES:
                    raise PublicFetchError('La página supera el tamaño permitido.')
                parts.append(chunk)
            if length is not None and total != declared:
                raise PublicFetchError('La página llegó incompleta. Reintenta explícitamente o pega el texto.')
            body = b''.join(parts)
            if not body.strip():
                raise PublicFetchError('La página está vacía.')
            if image:
                return {'body': body}
            charset = response.headers.get_content_charset() or 'utf-8'
            try:
                text = body.decode(charset, errors='replace')
            except LookupError:
                text = body.decode('utf-8', errors='replace')
            return {'html': text, 'sourceURL': canonical, 'statusCode': response.status}
        except (OSError, http.client.HTTPException) as error:
            raise PublicFetchError('No se pudo consultar la página de forma segura. Reintenta explícitamente o pega el texto.') from error
        finally:
            timer.cancel()
            if response:
                response.close()
            connection.abort()
    raise PublicFetchError('No se pudo consultar el enlace.')
