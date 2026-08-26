# 商品封面走本机代理：淘宝 CDN 含 !! 且防盗链，小程序 <image> 经常加载失败
from urllib.parse import quote, urlparse

_ALLOWED_HOST_SUFFIXES = (".alicdn.com",)
_ALLOWED_HOSTS = {
    "img.alicdn.com",
    "gw.alicdn.com",
    "images.unsplash.com",
}


def _host_allowed(host: str) -> bool:
    hostname = (host or "").lower().strip(".")
    if not hostname:
        return False
    if hostname in _ALLOWED_HOSTS:
        return True
    return any(hostname.endswith(suffix) for suffix in _ALLOWED_HOST_SUFFIXES)


def is_proxied_image_url(url: str) -> bool:
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in ("http", "https"):
        return False
    if parsed.username or parsed.password:
        return False
    return _host_allowed(parsed.hostname or "")


def proxied_media(url: str) -> str:
    value = (url or "").strip() if isinstance(url, str) else ""
    if not value:
        return ""
    if value.startswith("/uploads/") or value.startswith("/api/v1/"):
        return value
    if is_proxied_image_url(value):
        return "/api/v1/shop/cover-proxy?u=" + quote(value, safe="")
    return value
