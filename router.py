"""
router.py
---------
Validates and routes a parsed HTTP request to the appropriate calculator
operation.

Validation order (matches assignment spec):
    1. Method            → 405
    2. Path              → 404
    3. Host header       → 400
    4. Query params (a, b present) → 400
    5. Numeric values    → 400
    6. Division by zero  → 400
    7. Calculate         → 200

Returns (status: int, body: str).
"""

SUPPORTED_METHODS = {"GET"}
SUPPORTED_PATHS = {"/add", "/sub", "/mul", "/div"}


def route(request: dict) -> tuple[int, str]:
    """
    Validate *request* and return (status_code, body_text).

    *request* is the dict produced by http_parser.parse_request().
    """
    method = request["method"]
    path = request["path"]
    query = request["query"]
    headers = request["headers"]

    # 1. Method check
    if method not in SUPPORTED_METHODS:
        return 405, f"Method Not Allowed: {method}"

    # 2. Path check
    if path not in SUPPORTED_PATHS:
        return 404, f"Not Found: {path}"

    # 3. Host header required for HTTP/1.1
    if request.get("version") == "HTTP/1.1" and "host" not in headers:
        return 400, "Bad Request: missing Host header"

    # 4. Required query parameters
    if "a" not in query or "b" not in query:
        return 400, "Bad Request: missing query parameter(s) a and/or b"

    # 5. Numeric validation
    try:
        a = float(query["a"])
    except ValueError:
        return 400, f"Bad Request: non-numeric value for 'a': {query['a']!r}"

    try:
        b = float(query["b"])
    except ValueError:
        return 400, f"Bad Request: non-numeric value for 'b': {query['b']!r}"

    # 6. Division by zero
    if path == "/div" and b == 0:
        return 400, "Bad Request: division by zero"

    # 7. Calculate
    if path == "/add":
        result = a + b
    elif path == "/sub":
        result = a - b
    elif path == "/mul":
        result = a * b
    else:  # /div, b != 0 guaranteed above
        result = a / b

    # Format result: omit unnecessary .0 for whole numbers
    if result == int(result):
        body = str(int(result))
    else:
        body = str(result)

    return 200, body
