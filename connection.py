"""
connection.py
-------------
Manages one persistent TCP connection.

Key responsibilities:
- Maintain a per-connection receive buffer (byte buffer).
- Read from the socket until the header delimiter \\r\\n\\r\\n is found.
- Read exactly Content-Length body bytes (never more, never less).
- Preserve any leftover bytes in the buffer for the next request.
- Parse and route each request.
- Send the response.
- Loop until the client disconnects or a framing error occurs.

Design notes:
- Single-threaded and blocking (no asyncio, threads, or select).
- Semantic 400 errors (bad params, div-by-zero, etc.) do NOT close the
  connection because the request was completely and correctly framed.
- Only genuine framing failures (can't find \\r\\n\\r\\n, invalid
  Content-Length) close the connection, because in those cases we cannot
  trust where the current request ends.
"""

import socket

from http_parser import parse_request
from http_response import build_response
from router import route

RECV_SIZE = 4096  # bytes to read per recv() call
MAX_HEADER_SIZE = 64 * 1024  # 64 KB sanity cap for headers


def _recv_into_buffer(conn: socket.socket, buf: bytes) -> bytes:
    """
    Read one chunk from *conn* and append to *buf*.
    Returns updated buffer, or raises ConnectionError if the peer closed.
    """
    data = conn.recv(RECV_SIZE)
    if not data:
        raise ConnectionError("Client disconnected")
    return buf + data


def _read_headers(conn: socket.socket, buf: bytes) -> tuple[bytes, bytes]:
    """
    Read from *conn* until \\r\\n\\r\\n is found.

    Returns (header_bytes_without_delimiter, remainder_after_delimiter).

    header_bytes does NOT include the \\r\\n\\r\\n itself.

    Raises:
        ConnectionError  – peer closed before headers were complete.
        ValueError       – headers exceeded MAX_HEADER_SIZE (framing error).
    """
    while True:
        idx = buf.find(b"\r\n\r\n")
        if idx != -1:
            header_bytes = buf[:idx]
            remainder = buf[idx + 4:]
            return header_bytes, remainder

        if len(buf) > MAX_HEADER_SIZE:
            raise ValueError("Header section too large")

        buf = _recv_into_buffer(conn, buf)


def _read_body(conn: socket.socket, buf: bytes, length: int) -> tuple[bytes, bytes]:
    """
    Read exactly length bytes from the buffer (fetching more as needed).
    Returns (body_bytes, remainder_after_body).
    """
    while len(buf) < length:
        buf = _recv_into_buffer(conn, buf)

    body = buf[:length]
    remainder = buf[length:]
    return body, remainder


def handle_connection(conn: socket.socket, addr: tuple) -> None:
    """
    Process all HTTP requests on conn until the client disconnects or an
    unrecoverable framing error forces closure.
    """
    print(f"[connection] accepted from {addr}")
    buf = b""

    try:
        while True:
            try:
                header_bytes, buf = _read_headers(conn, buf)
            except ConnectionError:
                print("[connection] client disconnected (no more data)")
                return
            except ValueError as exc:
                print(f"[connection] header framing error: {exc}")
                _send_framing_error(conn)
                return


            framing_error = False
            request = None
            parse_exc_msg = ""

            try:
                request = parse_request(header_bytes)
            except ValueError as exc:
                parse_exc_msg = str(exc)
                framing_error = True

            if framing_error:
                print(f"[connection] request parse error: {parse_exc_msg}")
                _send_framing_error(conn)
                return


            content_length = 0
            raw_cl = request["headers"].get("content-length", "").strip()
            if raw_cl:
                try:
                    content_length = int(raw_cl)
                    if content_length < 0:
                        raise ValueError("negative Content-Length")
                except ValueError as exc:
                    print(f"[connection] invalid Content-Length: {exc}")
                    _send_framing_error(conn)
                    return

            if content_length > 0:
                try:
                    _body_bytes, buf = _read_body(conn, buf, content_length)
                except ConnectionError:
                    print("[connection] client disconnected while reading body")
                    return


            status, body = route(request)


            response_bytes = build_response(status, body, keep_alive=True)
            conn.sendall(response_bytes)

            print(
                f"[connection] {request['method']} {request['path']} "
                f"-> {status}  body={body!r}"
            )

    except OSError as exc:
        print(f"[connection] socket error: {exc}")
    finally:
        print(f"[connection] closing connection from {addr}")
        conn.close()


def _send_framing_error(conn: socket.socket) -> None:
    """
    Send a 400 Bad Request with Connection: close to signal unrecoverable framing error.
    """
    try:
        response = build_response(
            400,
            "Bad Request: unrecoverable framing error",
            keep_alive=False,
        )
        conn.sendall(response)
    except OSError:
        pass
