from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


def make_sync_url(url: str) -> str:
    """Convert the async application URL to the installed synchronous driver."""
    parsed = urlparse(url)
    scheme = "postgresql+psycopg2" if parsed.scheme.startswith("postgresql") else parsed.scheme
    query = urlencode(
        [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if key != "channel_binding"]
    )
    return urlunparse(parsed._replace(scheme=scheme, query=query))
