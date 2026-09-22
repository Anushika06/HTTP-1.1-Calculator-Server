# HTTP/1.1 Calculator Server

A minimal HTTP/1.1 calculator server built from scratch using raw TCP sockets — no web framework, no external dependencies, Python standard library only.

Built to demonstrate how HTTP actually works at the transport layer: TCP byte streams, request framing, `Content-Length`, and persistent keep-alive connections.

---

## Features

### Calculator API

| Request | Status | Body |
|---|---|---|
| `GET /add?a=2&b=3` | `200 OK` | `5` |
| `GET /sub?a=10&b=4` | `200 OK` | `6` |
| `GET /mul?a=6&b=7` | `200 OK` | `42` |
| `GET /div?a=9&b=3` | `200 OK` | `3` |
| `GET /div?a=1&b=0` | `400 Bad Request` | division by zero |
| `GET /add?a=x&b=3` | `400 Bad Request` | non-numeric value |
| `GET /add` | `400 Bad Request` | missing parameters |
| `GET /pow?a=2&b=8` | `404 Not Found` | unsupported path |
| `POST /add` | `405 Method Not Allowed` | only GET is supported |

### Validation order

```
Method → 405
Path   → 404
Host   → 400
Params → 400
Numeric → 400
Div/0  → 400
Calculate → 200
```

This order ensures `POST /add` always returns `405` — not `400` — even when the `Host` header is missing.

---

## Design decisions

- **Raw TCP sockets** — `socket.AF_INET` / `socket.SOCK_STREAM`, no HTTP framework.
- **Single-threaded, blocking, sequential** — one connection at a time; concurrency is intentionally out of scope. The goal is correct framing and persistent-connection logic, not throughput.
- **Persistent connections** — the server loops on one accepted socket, processing as many requests as the client sends, without calling `accept()` again.
- **Semantic errors do not close the connection** — a valid but semantically bad request (wrong params, div-by-zero) returns `400` and keeps the socket open. Only genuine framing failures close it.

---

## How it works

### Persistent connection loop

```
server.accept()
    │
    └─► while True:
            read headers  (buffer until \r\n\r\n)
            read body     (exactly Content-Length bytes)
            parse → route → respond
            ← same socket, next request
```

One `accept()` handles an unlimited number of HTTP requests.

### Request framing (the important part)

TCP is a byte stream — one `recv()` can return a fragment, one full request, or multiple requests merged together. The server handles all three cases correctly by maintaining a **persistent byte buffer per connection**:

```python
buffer = b""

# Phase 1 — accumulate until \r\n\r\n
while b"\r\n\r\n" not in buffer:
    buffer += conn.recv(4096)

header_bytes = buffer[:idx]
buffer       = buffer[idx + 4:]   # leftover belongs to next request

# Phase 2 — read exactly Content-Length body bytes
while len(buffer) < content_length:
    buffer += conn.recv(4096)

body   = buffer[:content_length]
buffer = buffer[content_length:]  # remainder = next request
```

Leftover bytes are **never discarded** — they are the start of the next request.

### Response format

```http
HTTP/1.1 200 OK
Content-Type: text/plain
Content-Length: 1
Connection: keep-alive

5
```

- `Content-Length` is always present and exact.
- Successful bodies have **no trailing newline** (`"5"` not `"5\n"`).
- `Connection: keep-alive` on all normal responses.

---

## Project structure

```
├── server.py        # TCP socket, bind/listen/accept loop
├── connection.py    # Per-connection keep-alive loop, byte buffer, framing
├── http_parser.py   # Request line, headers, query string parsing
├── router.py        # Validation and calculator operations → (status, body)
├── http_response.py # Build raw HTTP/1.1 response bytes
└── test_client.py   # Test suite — all tests over a single TCP socket
```

---

## Running

**Start the server:**
```bash
python server.py
```
```
[server] listening on localhost:8080
```

**Run the test suite** (in a second terminal):
```bash
python test_client.py
```
```
Results: 35/35 passed, 0 failed
```

---

## Manual testing with curl

```bash
curl.exe "http://localhost:8080/add?a=2&b=3"          # → 5
curl.exe "http://localhost:8080/mul?a=6&b=7"          # → 42
curl.exe "http://localhost:8080/div?a=1&b=0"          # → 400
curl.exe "http://localhost:8080/pow?a=2&b=8"          # → 404
curl.exe -X POST "http://localhost:8080/add"           # → 405

# See full HTTP headers
curl.exe -v "http://localhost:8080/add?a=2&b=3"
```

---

## Key tests

| Test | What it verifies |
|---|---|
| 7 requests on one socket | Keep-alive / persistent connection |
| Two requests in one `sendall()` | Server doesn't assume `recv() = request` |
| Request sent in two fragments | Server buffers partial data correctly |
| POST body + next GET in one send | Server consumes exactly `Content-Length` bytes |
| `400` then `200` on same socket | Semantic errors don't close the connection |
| `POST /add` (no Host) → `405` | Correct validation order |

---

## Concepts demonstrated

| Concept | Where |
|---|---|
| TCP byte stream buffering | `connection.py` — persistent `buf = b""` |
| HTTP request framing | `_read_headers()` / `_read_body()` |
| `Content-Length` as message boundary | `_read_body()` reads exactly N bytes |
| Persistent / keep-alive connections | `handle_connection()` inner loop |
| Framing error vs. semantic error | Connection closed only on framing failure |
| HTTP validation ordering | `router.py` — method before path before Host |

---

## Requirements

- Python 3.10+
- Standard library only (`socket`, `urllib.parse`)
