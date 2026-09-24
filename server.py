"""
Entry point for the HTTP/1.1 calculator server.
Single-threaded and blocking by design (concurrency out of scope).
"""

import socket

from connection import handle_connection

HOST = "localhost"
PORT = 8080
BACKLOG = 5


def main() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_sock:
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        server_sock.bind((HOST, PORT))
        server_sock.listen(BACKLOG)
        print(f"[server] listening on {HOST}:{PORT}")

        while True:
            conn, addr = server_sock.accept()
            handle_connection(conn, addr)


if __name__ == "__main__":
    main()
