"""Serve recommendations on the local loopback interface."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json

from model_review import with_model


class ReviewHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/review":
            self.send_error(404)
            return
        origin = self.headers.get("Origin", "")
        if self.headers.get("Host") != "127.0.0.1:8765" or (
            origin and not origin.startswith("chrome-extension://")
        ):
            self.send_error(403)
            return
        if self.headers.get_content_type() != "application/json":
            self.send_error(415)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 16384:
                raise ValueError
            request = json.loads(self.rfile.read(size))
            if not isinstance(request, dict):
                raise ValueError
        except ValueError:
            self.send_error(400, "Expected a JSON object up to 16 KiB")
            return

        payload = json.dumps(with_model(request), ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


if __name__ == "__main__":
    with ThreadingHTTPServer(("127.0.0.1", 8765), ReviewHandler) as server:
        print("Torob review agent listening on 127.0.0.1:8765", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
