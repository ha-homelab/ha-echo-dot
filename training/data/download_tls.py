# SPDX-License-Identifier: MIT
"""Verified TLS contexts for optional strict training downloads."""

import ssl


def client_context(*, strict=False, cafile=None):
    """Verify TLS and optionally enforce exact full-chain public-key minimums."""
    context = ssl.create_default_context(cafile=cafile)
    context.minimum_version = max(context.minimum_version, ssl.TLSVersion.TLSv1_2)
    if strict:
        if ssl.OPENSSL_VERSION_INFO < (3, 0, 0):
            raise RuntimeError("Strict TLS requires OpenSSL 3 or newer")
        if __package__:
            from .tls_key_policy import enforce_peer_key_policy
        else:
            from tls_key_policy import enforce_peer_key_policy
        context = enforce_peer_key_policy(context)
    return context



def open_source(request, *, timeout=60):
    """Retain the verified context on every redirect in the opt-in profile."""
    import os
    import urllib.parse
    import urllib.request

    mode = os.environ.get("ECHO_DOT_STRICT_TLS", "0")
    if mode not in {"0", "1"}:
        raise ValueError("ECHO_DOT_STRICT_TLS must be 0 or 1")
    if mode == "0":
        return urllib.request.urlopen(request, timeout=timeout)
    url = request.full_url if isinstance(request, urllib.request.Request) else request
    if urllib.parse.urlsplit(url).scheme != "https":
        raise ValueError("Strict training downloads require HTTPS")

    class SecureRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, request, fp, code, msg, headers, newurl):
            if urllib.parse.urlsplit(newurl).scheme != "https":
                raise ValueError("Strict training downloads reject non-HTTPS redirects")
            return super().redirect_request(request, fp, code, msg, headers, newurl)

    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=client_context(strict=True)), SecureRedirect())
    return opener.open(request, timeout=timeout)
