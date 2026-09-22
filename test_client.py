"""
test_client.py
--------------
Comprehensive test client for the HTTP/1.1 calculator server.

All tests are run over a SINGLE TCP connection (one socket.create_connection
call for the main test sequence). A separate connection is used only for
isolated framing tests that intentionally break the connection.

Run with:
    python test_client.py

The server must be running first:
    python server.py

Exit code: 0 if all tests pass, 1 if any fail.
"""

import socket
import sys
import time

HOST = "localhost"
PORT = 8080
RECV_SIZE = 4096


# ---------------------------------------------------------------------------
# Buffered socket wrapper
# Maintains a per-socket byte buffer so that leftover bytes from one
# recv_response() call are available for the next call on the same socket.
# This is essential for the concatenated-request test where the server may
# return two responses in rapid succession and a single sock.recv() may
# contain both.
# ---------------------------------------------------------------------------

class BufferedSocket:
    """Thin wrapper around a socket that maintains a persistent read buffer."""

    def __init__(self, sock: socket.socket) -> None:
        self._sock = sock
        self._buf = b""

    def sendall(self, data: bytes) -> None:
        self._sock.sendall(data)

    def send(self, data: bytes) -> int:
        return self._sock.send(data)

    def close(self) -> None:
        self._sock.close()

    def recv_response(self) -> tuple[int, str, str]:
        """
        Read exactly one HTTP response from the socket, using the internal
        buffer to avoid discarding leftover bytes between calls.

        Returns (status_code, headers_text, body_text).
        """
        # Phase 1: read until the header terminator is found
        while b"\r\n\r\n" not in self._buf:
            chunk = self._sock.recv(RECV_SIZE)
            if not chunk:
                raise ConnectionError("Server closed connection while reading headers")
            self._buf += chunk

        idx = self._buf.index(b"\r\n\r\n")
        header_section = self._buf[:idx].decode("latin-1")
        self._buf = self._buf[idx + 4:]  # remainder after blank line

        # Phase 2: parse status code
        status_line = header_section.split("\r\n")[0]
        parts = status_line.split(" ", 2)
        status_code = int(parts[1])

        # Phase 3: parse Content-Length
        content_length = 0
        for line in header_section.split("\r\n")[1:]:
            if line.lower().startswith("content-length:"):
                content_length = int(line.split(":", 1)[1].strip())
                break

        # Phase 4: read exactly content_length body bytes
        while len(self._buf) < content_length:
            chunk = self._sock.recv(RECV_SIZE)
            if not chunk:
                raise ConnectionError("Server closed connection while reading body")
            self._buf += chunk

        body = self._buf[:content_length].decode("utf-8")
        self._buf = self._buf[content_length:]  # preserve remainder for next call

        return status_code, header_section, body


def connect() -> BufferedSocket:
    """Create a new TCP connection to the server."""
    raw = socket.create_connection((HOST, PORT))
    raw.settimeout(5.0)
    return BufferedSocket(raw)


# ---------------------------------------------------------------------------
# Request builders
# ---------------------------------------------------------------------------

def make_get(path: str, *, host: str = "localhost", extra_headers: str = "") -> bytes:
    """Build a minimal GET request."""
    req = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        f"{extra_headers}"
        f"\r\n"
    )
    return req.encode()


def make_post(path: str, body: str = "", *, host: str = "localhost") -> bytes:
    """Build a minimal POST request."""
    body_bytes = body.encode()
    req = (
        f"POST {path} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        f"Content-Length: {len(body_bytes)}\r\n"
        f"\r\n"
    )
    return req.encode() + body_bytes


# ---------------------------------------------------------------------------
# Test framework
# ---------------------------------------------------------------------------

_pass = 0
_fail = 0


def check(label: str, actual, expected, *, info: str = "") -> None:
    global _pass, _fail
    if actual == expected:
        print(f"  PASS  {label}")
        _pass += 1
    else:
        print(f"  FAIL  {label}")
        print(f"        expected: {expected!r}")
        print(f"        actual:   {actual!r}")
        if info:
            print(f"        info:     {info}")
        _fail += 1


# ---------------------------------------------------------------------------
# Test suites
# ---------------------------------------------------------------------------

def test_basic_operations(bsock: BufferedSocket) -> None:
    """Send the seven required requests over one socket."""
    print("\n=== Test: Basic operations (single socket) ===")

    cases = [
        # (path,              expected_status, expected_body)
        ("/add?a=2&b=3",      200, "5"),
        ("/sub?a=10&b=4",     200, "6"),
        ("/mul?a=6&b=7",      200, "42"),
        ("/div?a=9&b=3",      200, "3"),
        ("/div?a=1&b=0",      400, None),   # division by zero
        ("/pow?a=2&b=8",      404, None),   # unknown path
    ]

    for path, exp_status, exp_body in cases:
        bsock.sendall(make_get(path))
        status, _headers, body = bsock.recv_response()
        check(f"GET {path} -> {exp_status}", status, exp_status)
        if exp_body is not None:
            check(f"  body = {exp_body!r}", body, exp_body)


def test_post_method(bsock: BufferedSocket) -> None:
    """POST /add should return 405, not 400."""
    print("\n=== Test: POST /add -> 405 ===")
    bsock.sendall(make_post("/add"))
    status, _headers, _body = bsock.recv_response()
    check("POST /add -> 405", status, 405)


def test_missing_host(bsock: BufferedSocket) -> None:
    """GET /add without Host header should return 400 (after method/path pass)."""
    print("\n=== Test: Missing Host header -> 400 ===")
    req = b"GET /add?a=1&b=2 HTTP/1.1\r\n\r\n"  # no Host
    bsock.sendall(req)
    status, _headers, _body = bsock.recv_response()
    check("GET /add (no Host) -> 400", status, 400)


def test_missing_params(bsock: BufferedSocket) -> None:
    """GET /add with no query params should return 400."""
    print("\n=== Test: Missing query params -> 400 ===")
    bsock.sendall(make_get("/add"))  # no ?a=...&b=...
    status, _headers, _body = bsock.recv_response()
    check("GET /add (no params) -> 400", status, 400)


def test_invalid_number(bsock: BufferedSocket) -> None:
    """GET /add?a=x&b=3 should return 400."""
    print("\n=== Test: Non-numeric value -> 400 ===")
    bsock.sendall(make_get("/add?a=x&b=3"))
    status, _headers, _body = bsock.recv_response()
    check("GET /add?a=x&b=3 -> 400", status, 400)


def test_connection_stays_open_after_400(bsock: BufferedSocket) -> None:
    """
    Test D: After a semantic 400, the connection must remain open.
    Send /div?a=1&b=0  (400) then /add?a=2&b=3 (200) on the SAME socket.
    """
    print("\n=== Test D: Connection alive after semantic 400 ===")
    bsock.sendall(make_get("/div?a=1&b=0"))
    status1, _, _ = bsock.recv_response()
    check("div-by-zero -> 400", status1, 400)

    bsock.sendall(make_get("/add?a=2&b=3"))
    status2, _, body2 = bsock.recv_response()
    check("subsequent /add -> 200", status2, 200)
    check("body is '5'", body2, "5")


def test_concatenated_requests(bsock: BufferedSocket) -> None:
    """
    Test A: Send two complete requests in a single sendall().
    Server must not assume one recv() == one request.
    The buffered client correctly accumulates responses.
    """
    print("\n=== Test A: Concatenated requests (one sendall) ===")
    combined = make_get("/add?a=1&b=1") + make_get("/mul?a=3&b=4")
    bsock.sendall(combined)

    status1, _, body1 = bsock.recv_response()
    check("concat req 1 -> 200", status1, 200)
    check("concat body 1 = '2'", body1, "2")

    status2, _, body2 = bsock.recv_response()
    check("concat req 2 -> 200", status2, 200)
    check("concat body 2 = '12'", body2, "12")


def test_fragmented_request(bsock: BufferedSocket) -> None:
    """
    Test B: Send one request across multiple small sends.
    Server must buffer until it has a complete request.
    """
    print("\n=== Test B: Fragmented request ===")
    req = make_get("/sub?a=20&b=5")

    # Send in two pieces with a small sleep to encourage separate recv() calls
    mid = len(req) // 2
    bsock.send(req[:mid])
    time.sleep(0.05)
    bsock.send(req[mid:])

    status, _, body = bsock.recv_response()
    check("fragmented /sub -> 200", status, 200)
    check("fragmented body = '15'", body, "15")


def test_body_boundary(bsock: BufferedSocket) -> None:
    """
    Test C: Send a POST with a body immediately followed by another request.
    Server must consume exactly Content-Length bytes for the first request
    and leave the second request's bytes intact in its buffer.
    """
    print("\n=== Test C: Body boundary (POST body + next request) ===")
    body_text = "hello"
    post_req = make_post("/add", body_text)    # POST /add -> 405
    get_req = make_get("/add?a=7&b=8")          # GET /add -> 200

    # Send both in one call so they may arrive in the same recv() on the server
    bsock.sendall(post_req + get_req)

    # First response: POST -> 405
    status1, _, _ = bsock.recv_response()
    check("body-boundary: POST /add -> 405", status1, 405)

    # Second response: GET /add -> 200  (body must not have been consumed)
    status2, _, body2 = bsock.recv_response()
    check("body-boundary: GET /add -> 200", status2, 200)
    check("body-boundary: body = '15'", body2, "15")


def test_triple_concatenated(bsock: BufferedSocket) -> None:
    """
    Test E: Three requests pipelined in one send.
    """
    print("\n=== Test E: Triple pipelined requests ===")
    reqs = (
        make_get("/add?a=10&b=10")
        + make_get("/sub?a=100&b=1")
        + make_get("/div?a=8&b=2")
    )
    bsock.sendall(reqs)

    exp = [(200, "20"), (200, "99"), (200, "4")]
    for i, (exp_status, exp_body) in enumerate(exp, 1):
        status, _, body = bsock.recv_response()
        check(f"triple[{i}] status -> {exp_status}", status, exp_status)
        check(f"triple[{i}] body = {exp_body!r}", body, exp_body)


def test_content_length_exact(bsock: BufferedSocket) -> None:
    """Verify Content-Length in responses matches actual body length."""
    print("\n=== Test: Response Content-Length accuracy ===")
    cases = [
        ("/add?a=2&b=3",  "5"),
        ("/mul?a=6&b=7", "42"),
    ]
    for path, exp_body in cases:
        bsock.sendall(make_get(path))
        status, headers, body = bsock.recv_response()
        cl = None
        for line in headers.split("\r\n"):
            if line.lower().startswith("content-length:"):
                cl = int(line.split(":", 1)[1].strip())
        check(
            f"Content-Length matches body for {path}",
            cl,
            len(exp_body.encode("utf-8")),
        )


def test_post_without_host(bsock: BufferedSocket) -> None:
    """
    POST /add without Host -> must still be 405, not 400.
    (Method validation must happen before Host validation.)
    """
    print("\n=== Test: POST /add no Host -> 405 (not 400) ===")
    req = b"POST /add HTTP/1.1\r\n\r\n"
    bsock.sendall(req)
    status, _, _ = bsock.recv_response()
    check("POST /add (no Host) -> 405", status, 405)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"Starting test suite against server at {HOST}:{PORT}")

    # -------------------------------------------------------------------
    # Main socket - all basic tests run over this ONE connection
    # -------------------------------------------------------------------
    try:
        main_sock = connect()
    except ConnectionRefusedError:
        print("\nERROR: Cannot connect to server. Is 'python server.py' running?")
        sys.exit(1)

    try:
        test_basic_operations(main_sock)
        test_post_method(main_sock)
        test_missing_host(main_sock)
        test_missing_params(main_sock)
        test_invalid_number(main_sock)
        test_connection_stays_open_after_400(main_sock)
        test_concatenated_requests(main_sock)
        test_fragmented_request(main_sock)
        test_content_length_exact(main_sock)
        test_post_without_host(main_sock)
        test_triple_concatenated(main_sock)
    finally:
        main_sock.close()

    # -------------------------------------------------------------------
    # Separate socket for body-boundary test
    # -------------------------------------------------------------------
    try:
        bb_sock = connect()
        try:
            test_body_boundary(bb_sock)
        finally:
            bb_sock.close()
    except ConnectionRefusedError:
        print("\nERROR: Cannot connect for body-boundary test.")

    # -------------------------------------------------------------------
    # Connection reuse note
    # -------------------------------------------------------------------
    print("\n=== Test: Connection reuse ===")
    print("  INFO  All tests sharing 'main_sock' used ONE TCP connection.")
    print("  INFO  Check server output - '[connection] accepted' appears once per socket.")

    # -------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------
    total = _pass + _fail
    print(f"\n{'='*50}")
    print(f"Results: {_pass}/{total} passed, {_fail} failed")
    print("=" * 50)

    if _fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
