"""
http_parser.py
--------------
Parses a raw HTTP/1.1 request into structured data.

Input:  raw bytes up to and including the blank line (\\r\\n\\r\\n).
Output: dict with keys method, path, query, version, headers.

Raises ValueError for malformed request syntax.
"""

from urllib.parse import urlparse, parse_qs


def parse_request(header_bytes: bytes) -> dict:
    """
    Parse the header section of an HTTP request (everything up to and
    including the blank line, but NOT the body).

    Returns a dict:
        {
            "method":  str,          # e.g. "GET"
            "path":    str,          # e.g. "/add"
            "query":   dict[str, str],  # first value per key, e.g. {"a": "2", "b": "3"}
            "version": str,          # e.g. "HTTP/1.1"
            "headers": dict[str, str],  # lowercase keys, e.g. {"host": "localhost"}
        }

    Raises ValueError on malformed syntax.
    """
    try:
        text = header_bytes.decode("latin-1")
    except Exception:
        raise ValueError("Could not decode request headers")

    # Split into lines; HTTP lines are separated by \r\n
    lines = text.split("\r\n")
    if not lines:
        raise ValueError("Empty request")

    # --- Request line ---
    request_line = lines[0]
    parts = request_line.split(" ")
    if len(parts) != 3:
        raise ValueError(f"Malformed request line: {request_line!r}")

    method, raw_target, version = parts[0], parts[1], parts[2]

    if not method or not raw_target or not version:
        raise ValueError("Empty field in request line")

    # --- Parse path and query string ---
    parsed = urlparse(raw_target)
    path = parsed.path or "/"

    # parse_qs returns lists; keep only the first value per key
    qs_dict = parse_qs(parsed.query, keep_blank_values=True)
    query = {k: v[0] for k, v in qs_dict.items()}

    # --- Parse headers ---
    headers: dict[str, str] = {}
    for line in lines[1:]:
        if line == "":
            break  # blank line marks end of headers
        if ":" not in line:
            raise ValueError(f"Malformed header line: {line!r}")
        name, _, value = line.partition(":")
        headers[name.strip().lower()] = value.strip()

    return {
        "method": method,
        "path": path,
        "query": query,
        "version": version,
        "headers": headers,
    }
