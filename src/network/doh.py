"""
DNS-over-HTTPS (DoH) Resolver Module.
Provides automatic DNS resolution via Cloudflare / Google DoH to bypass
ISP DNS hijacking/blocking (common with crypto exchanges in certain regions like Indonesia).
"""

import json
import logging
import socket
import urllib.request
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Cache for resolved domain names -> list of IP addresses
_DNS_CACHE: Dict[str, List[str]] = {}
_REAL_GETADDRINFO = socket.getaddrinfo
_PATCHED = False

# Domains known to be targeted by ISP blocks
DEFAULT_TARGET_DOMAINS = [
    "binance.com",
    "fapi.binance.com",
    "api.binance.com",
    "bybit.com",
    "api.bybit.com",
    "gate.io",
    "api.gateio.ws",
    "okx.com",
    "api.okx.com",
    "kucoin.com",
    "api.kucoin.com",
]


def resolve_doh(domain: str, timeout: float = 4.0) -> List[str]:
    """Resolve an A record for domain using Cloudflare or Google DoH."""
    if domain in _DNS_CACHE:
        return _DNS_CACHE[domain]

    # 1. Try Cloudflare DoH
    cf_url = f"https://cloudflare-dns.com/dns-query?name={domain}&type=A"
    try:
        req = urllib.request.Request(cf_url, headers={"accept": "application/dns-json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            ips = [ans["data"] for ans in data.get("Answer", []) if ans.get("type") == 1]
            if ips:
                _DNS_CACHE[domain] = ips
                return ips
    except Exception as e:
        logger.debug(f"Cloudflare DoH failed for {domain}: {e}")

    # 2. Fallback to Google DoH
    g_url = f"https://dns.google/resolve?name={domain}&type=A"
    try:
        req = urllib.request.Request(g_url, headers={"accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            ips = [ans["data"] for ans in data.get("Answer", []) if ans.get("type") == 1]
            if ips:
                _DNS_CACHE[domain] = ips
                return ips
    except Exception as e:
        logger.debug(f"Google DoH failed for {domain}: {e}")

    return []


def enable_doh(target_domains: Optional[List[str]] = None) -> None:
    """Monkey-patch socket.getaddrinfo to resolve target domains via DoH."""
    global _PATCHED
    if _PATCHED:
        return

    domains = target_domains or DEFAULT_TARGET_DOMAINS

    def custom_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        if host and any(d in host for d in domains):
            ips = resolve_doh(host)
            if ips:
                # Use first resolved DoH IP
                return _REAL_GETADDRINFO(ips[0], port, family, type, proto, flags)
        return _REAL_GETADDRINFO(host, port, family, type, proto, flags)

    socket.getaddrinfo = custom_getaddrinfo
    _PATCHED = True
    logger.info("DNS-over-HTTPS (DoH) resolver enabled for crypto exchange domains.")


def disable_doh() -> None:
    """Restore original socket.getaddrinfo."""
    global _PATCHED
    if _PATCHED:
        socket.getaddrinfo = _REAL_GETADDRINFO
        _PATCHED = False
        logger.info("DoH resolver disabled.")
