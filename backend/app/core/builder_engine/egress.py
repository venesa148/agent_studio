"""Egress guard: allowlist host + anti-SSRF. Semua request keluar tool wajib lewat sini."""
import ipaddress
import socket
from urllib.parse import urlparse


class Blocked(Exception):
    pass


def host_allowed(host: str, allowed: list[str]) -> bool:
    h = host.lower()
    return any(h == a or (a.startswith("*.") and h.endswith(a[1:])) for a in allowed)


def _resolve(host: str) -> list[str]:
    return [i[4][0] for i in socket.getaddrinfo(host, 443)]


def check_url(url: str, allowed_hosts: list[str], resolve=_resolve) -> str:
    u = urlparse(url)
    if u.scheme != "https":
        raise Blocked("scheme")
    if u.username or u.password:
        raise Blocked("credentials")
    if u.port not in (None, 443):
        raise Blocked("port")
    host = u.hostname or ""
    if not host_allowed(host, allowed_hosts):
        raise Blocked("host_not_allowed")
    for ip in resolve(host):
        a = ipaddress.ip_address(ip)
        if a.is_private or a.is_loopback or a.is_link_local or a.is_reserved or a.is_multicast or a.is_unspecified:
            raise Blocked("private_ip")  # termasuk 169.254.169.254 (metadata cloud)
    return url
