"""
Validates and routes a parsed HTTP request to the appropriate calculator operation.
"""

SUPPORTED_METHODS = {"GET"}
SUPPORTED_PATHS = {"/add", "/sub", "/mul", "/div"}


def route(request: dict) -> tuple[int, str]:
    method = request["method"]
    path = request["path"]
    query = request["query"]
    headers = request["headers"]

    if method not in SUPPORTED_METHODS:
        return 405, f"Method Not Allowed: {method}"

    if path not in SUPPORTED_PATHS:
        return 404, f"Not Found: {path}"

    if request.get("version") == "HTTP/1.1" and "host" not in headers:
        return 400, "Bad Request: missing Host header"

    if "a" not in query or "b" not in query:
        return 400, "Bad Request: missing query parameter(s) a and/or b"

    try:
        a = float(query["a"])
    except ValueError:
        return 400, f"Bad Request: non-numeric value for 'a': {query['a']!r}"

    try:
        b = float(query["b"])
    except ValueError:
        return 400, f"Bad Request: non-numeric value for 'b': {query['b']!r}"

    if path == "/div" and b == 0:
        return 400, "Bad Request: division by zero"

    if path == "/add":
        result = a + b
    elif path == "/sub":
        result = a - b
    elif path == "/mul":
        result = a * b
    else:
        result = a / b

    if result == int(result):
        body = str(int(result))
    else:
        body = str(result)

    return 200, body
