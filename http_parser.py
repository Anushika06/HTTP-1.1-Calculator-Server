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
    try:
        text = header_bytes.decode("latin-1")
    except Exception:
        raise ValueError("Could not decode request headers")

    lines = text.split("\r\n")
    if not lines:
        raise ValueError("Empty request")

    request_line = lines[0]
    parts = request_line.split(" ")
    if len(parts) != 3:
        raise ValueError(f"Malformed request line: {request_line!r}")

    method, raw_target, version = parts[0], parts[1], parts[2]

    if not method or not raw_target or not version:
        raise ValueError("Empty field in request line")

    parsed = urlparse(raw_target)
    path = parsed.path or "/"

    qs_dict = parse_qs(parsed.query, keep_blank_values=True)
    query = {k: v[0] for k, v in qs_dict.items()}

    headers: dict[str, str] = {}
    for line in lines[1:]:
        if line == "":
            break
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
