"""
http_response.py
----------------
Builds raw HTTP/1.1 response bytes.
"""

REASON_PHRASES = {
    200: "OK",
    400: "Bad Request",
    404: "Not Found",
    405: "Method Not Allowed",
    500: "Internal Server Error",
}


def build_response(
    status: int,
    body: str,
    *,
    content_type: str = "text/plain",
    extra_headers: dict | None = None,
    keep_alive: bool = True,
) -> bytes:
    """
    Build a complete HTTP/1.1 response as bytes.

    Args:
        status:        HTTP status code.
        body:          Response body text (no trailing newline required).
        content_type:  Value for Content-Type header.
        extra_headers: Additional headers to include (dict[str, str]).
        keep_alive:    If True, send 'Connection: keep-alive';
                       if False, send 'Connection: close'.

    Returns:
        Raw bytes ready to be sent via sendall().
    """
    reason = REASON_PHRASES.get(status, "Unknown")
    body_bytes = body.encode("utf-8")

    connection_value = "keep-alive" if keep_alive else "close"

    headers = [
        f"HTTP/1.1 {status} {reason}",
        f"Content-Type: {content_type}",
        f"Content-Length: {len(body_bytes)}",
        f"Connection: {connection_value}",
    ]

    if extra_headers:
        for name, value in extra_headers.items():
            headers.append(f"{name}: {value}")

    # Blank line separates headers from body
    raw = "\r\n".join(headers) + "\r\n\r\n"
    return raw.encode("utf-8") + body_bytes
