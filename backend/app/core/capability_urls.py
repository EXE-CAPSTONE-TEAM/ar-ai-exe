from urllib.parse import urlsplit


def canonical_origin(
    value: str,
    *,
    origin_only: bool,
    require_https: bool,
) -> str:
    """Return a normalized HTTP(S) origin or reject ambiguous URL forms."""
    if not value or any(ord(character) < 32 for character in value) or "\\" in value:
        raise ValueError("invalid URL characters")

    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise ValueError("invalid URL")
    if require_https and parsed.scheme != "https":
        raise ValueError("HTTPS is required")

    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("invalid URL port") from exc

    if origin_only:
        if parsed.path not in {"", "/"} or parsed.query:
            raise ValueError("allowlist entries must be origins")
    elif parsed.path in {"", "/"}:
        raise ValueError("capability URL must address an object")

    host = parsed.hostname.lower()
    if ":" in host:
        normalized_host = f"[{host}]"
    else:
        normalized_host = host.encode("idna").decode("ascii")

    default_port = 443 if parsed.scheme == "https" else 80
    port_suffix = f":{port}" if port and port != default_port else ""
    return f"{parsed.scheme}://{normalized_host}{port_suffix}"
