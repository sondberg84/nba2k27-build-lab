import json
import threading
import unittest
import urllib.error
import urllib.request

from buildlab import server


class TestServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = server.build(port=0)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=5)

    def url(self, path):
        return f"http://127.0.0.1:{self.port}{path}"

    def get(self, path):
        with urllib.request.urlopen(self.url(path)) as response:
            return response.status, response.read()

    def post(self, path, payload):
        request = urllib.request.Request(
            self.url(path),
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read())

    def test_it_binds_to_localhost_only(self):
        self.assertEqual(self.httpd.server_address[0], "127.0.0.1")

    def test_the_index_page_is_served(self):
        status, body = self.get("/")
        self.assertEqual(status, 200)
        self.assertIn(b"<html", body.lower())

    def test_static_assets_are_served(self):
        for path in ("/style.css", "/app.js"):
            with self.subTest(path=path):
                status, _ = self.get(path)
                self.assertEqual(status, 200)

    def test_health_reports_the_pinned_commit(self):
        status, body = self.get("/api/health")
        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(len(payload["commit"]), 40)
        self.assertTrue(payload["hashes_ok"])

    def test_meta_is_served(self):
        status, body = self.get("/api/meta")
        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(len(payload["attributes"]), 21)

    def test_evaluate_returns_a_result(self):
        status, payload = self.post(
            "/api/evaluate", {"height": 76, "values": [70] * 21}
        )
        self.assertEqual(status, 200)
        self.assertIn("overall", payload)

    def test_ladder_returns_steps(self):
        status, payload = self.post(
            "/api/ladder", {"height": 76, "attribute": "ball_handle"}
        )
        self.assertEqual(status, 200)
        self.assertGreater(len(payload["steps"]), 0)

    def test_a_bad_request_returns_400_with_a_message(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.post("/api/evaluate", {"height": 76, "values": [70] * 20})
        self.assertEqual(caught.exception.code, 400)
        body = json.loads(caught.exception.read())
        self.assertIn("21", body["error"])

    def test_an_unknown_path_returns_404(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.get("/nope")
        self.assertEqual(caught.exception.code, 404)

    def test_traversal_outside_the_ui_directory_is_refused(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.get("/../buildlab/ovr.py")
        self.assertIn(caught.exception.code, (400, 403, 404))


if __name__ == "__main__":
    unittest.main()
