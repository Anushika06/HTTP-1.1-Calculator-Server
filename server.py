"""
server.py
---------
Entry point for the HTTP/1.1 calculator server.

Creates a raw TCP socket, binds to localhost:8080, and loops accepting
connections. Each accepted connection is handed off to connection.handle_connection()
for keep-alive processing of multiple HTTP/1.1 requests.

Single-threaded and blocking by design — concurrency is intentionally out
of scope for this assignment.
"""

import socket

from connection import handle_connection

HOST = "localhost"
PORT = 8080
BACKLOG = 5


def main() -> None:
    # Create an IPv4 TCP socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_sock:
        # Allow quick restart without 'address already in use' errors
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        server_sock.bind((HOST, PORT))
        server_sock.listen(BACKLOG)
        print(f"[server] listening on {HOST}:{PORT}")

        while True:
            # Block until a client connects
            conn, addr = server_sock.accept()
            # Process all requests on this one connection (keep-alive)
            handle_connection(conn, addr)
            # After handle_connection returns, go back and accept the next client


if __name__ == "__main__":
    main()
