from hashlib import sha256


def build_web_source_id(
    url: str,
) -> str:
    """Build one stable source ID from a web URL."""

    digest = sha256(
        url.encode("utf-8")
    ).hexdigest()

    return f"web_{digest[:16]}"
