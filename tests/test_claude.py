"""Claude layer tests against a fake HTTP transport: no network, no API key, no cost."""

import json
import threading
import time
import unittest

try:
    import anthropic
    import httpx2
    from gi.repository import GLib

    from bangla_ai import claude
    from bangla_ai.config import DEFAULTS
except ImportError as e:  # anthropic is only in the app's venv
    SKIP_REASON = f"needs the app's dependencies: {e}"
else:
    SKIP_REASON = None


def _message(payload, stop_reason="end_turn"):
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": "claude-opus-5-5",
        "content": [{"type": "text", "text": text}],
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }


@unittest.skipIf(SKIP_REASON, SKIP_REASON)
class SuggesterFetchTest(unittest.TestCase):
    def make(self, handler, **overrides):
        self.requests = []

        def recording_handler(request):
            self.requests.append(request)
            return handler(request)

        config = dict(DEFAULTS, **overrides)
        suggester = claude.Suggester(config)
        suggester._client = anthropic.Anthropic(
            api_key="test-key",
            max_retries=0,
            http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(recording_handler)),
        )
        self.addCleanup(suggester.shutdown)
        return suggester

    def body(self, index=0):
        return json.loads(self.requests[index].content)

    def test_fallback_model_request_shape(self):
        s = self.make(lambda r: httpx2.Response(200, json=_message({"words": ["করবো"], "completion": " আমি"})),
                      model="claude-opus-5-5")
        result = s._fetch("আমি ", "korbo")
        self.assertEqual(result.words, ["করবো"])
        self.assertEqual(result.completion, " আমি")
        self.assertIsNone(s.status)

        request = self.requests[0]
        self.assertIn("server-side-fallback-2026-07-01", request.headers.get("anthropic-beta", ""))
        body = self.body()
        self.assertEqual(body["model"], "claude-opus-5-5")
        self.assertEqual(body["fallbacks"], "default")
        self.assertEqual(body["output_config"]["effort"], "low")
        self.assertEqual(body["output_config"]["format"]["type"], "json_schema")
        self.assertNotIn("thinking", body)
        self.assertEqual(json.loads(body["messages"][0]["content"]), {"context": "আমি ", "current_input": "korbo"})

    def test_default_model_is_haiku_without_fallbacks(self):
        s = self.make(lambda r: httpx2.Response(200, json=_message({"words": [], "completion": ""})))
        s._fetch("", "ami")
        self.assertEqual(self.body()["model"], "claude-haiku-5-5")
        self.assertEqual(self.body()["output_config"]["effort"], "low")
        self.assertNotIn("fallbacks", self.body())
        self.assertNotIn("server-side-fallback", self.requests[0].headers.get("anthropic-beta", ""))

    def test_auth_error_resets_client(self):
        s = self.make(lambda r: httpx2.Response(401, json={"type": "error", "error": {"type": "authentication_error", "message": "bad key"}}))
        self.assertIsNone(s._fetch("", "ami"))
        self.assertEqual(s.status, "auth")
        self.assertIsNone(s._client)
        self.assertGreater(s._backoff_until, time.monotonic())

    def test_rate_limit_uses_retry_after(self):
        s = self.make(lambda r: httpx2.Response(429, headers={"retry-after": "12"},
                                                json={"type": "error", "error": {"type": "rate_limit_error", "message": "slow"}}))
        self.assertIsNone(s._fetch("", "ami"))
        self.assertEqual(s.status, "rate-limit")
        self.assertGreater(s._backoff_until, time.monotonic() + 10)

    def test_offline(self):
        def fail(request):
            raise httpx2.ConnectError("no network", request=request)

        s = self.make(fail)
        self.assertIsNone(s._fetch("", "ami"))
        self.assertEqual(s.status, "offline")

    def test_refusal_gives_nothing(self):
        s = self.make(lambda r: httpx2.Response(200, json=_message("", stop_reason="refusal")))
        self.assertIsNone(s._fetch("", "ami"))

    def test_invalid_json_gives_nothing(self):
        s = self.make(lambda r: httpx2.Response(200, json=_message("not json")))
        self.assertIsNone(s._fetch("", "ami"))

    def test_request_calls_back_on_main_loop_and_caches(self):
        s = self.make(lambda r: httpx2.Response(200, json=_message({"words": ["আমি"], "completion": ""})))
        results = []
        context = GLib.MainContext.default()
        for _ in range(2):
            self.assertTrue(s.request("", "ami", results.append))
            deadline = time.monotonic() + 5
            count = len(results)
            while len(results) == count and time.monotonic() < deadline:
                context.iteration(False)
                time.sleep(0.01)
        self.assertEqual([r.words for r in results], [["আমি"], ["আমি"]])
        self.assertEqual(len(self.requests), 1)  # the second answer came from the cache

    def test_cache_ignores_older_context(self):
        s = self.make(lambda r: httpx2.Response(200, json=_message({"words": ["যাবো"], "completion": ""})))
        results = []
        context = GLib.MainContext.default()
        for before in ("আজ সকালে আমি বাড়ি ", "কাল সকালে আমি বাড়ি "):
            s.request(before, "jabo", results.append)
            deadline = time.monotonic() + 5
            count = len(results)
            while len(results) == count and time.monotonic() < deadline:
                context.iteration(False)
                time.sleep(0.01)
        self.assertEqual(len(results), 2)
        self.assertEqual(len(self.requests), 1)  # same last words -> answered from the cache

    def test_newer_request_replaces_waiting_one(self):
        release = threading.Event()

        def slow(request):
            release.wait(5)
            word = json.loads(json.loads(request.content)["messages"][0]["content"])["current_input"]
            return httpx2.Response(200, json=_message({"words": [word.upper()], "completion": ""}))

        s = self.make(slow)
        results = []
        s.request("", "a", lambda r: results.append(("a", r)))  # starts right away
        time.sleep(0.1)
        s.request("", "ab", lambda r: results.append(("ab", r)))  # waits ...
        s.request("", "abc", lambda r: results.append(("abc", r)))  # ... and is replaced by this
        release.set()
        context = GLib.MainContext.default()
        deadline = time.monotonic() + 5
        while len(results) < 2 and time.monotonic() < deadline:
            context.iteration(False)
            time.sleep(0.01)
        time.sleep(0.1)
        context.iteration(False)
        self.assertEqual([name for name, _ in results], ["a", "abc"])
        sent = [json.loads(json.loads(r.content)["messages"][0]["content"])["current_input"] for r in self.requests]
        self.assertEqual(sent, ["a", "abc"])

    def test_backoff_skips_request(self):
        s = self.make(lambda r: httpx2.Response(200, json=_message({"words": [], "completion": ""})))
        s._backoff_until = time.monotonic() + 60
        self.assertFalse(s.request("", "ami", lambda result: None))


@unittest.skipIf(SKIP_REASON, SKIP_REASON)
class CleanTest(unittest.TestCase):
    def test_filters_words(self):
        result = claude._clean({"words": ["আমি", "ami", "আমি", "তুমি\nসে", 5, "সে", "ও"], "completion": "ভাত\nখাই"}, 3)
        self.assertEqual(result.words, ["আমি", "সে", "ও"])
        self.assertEqual(result.completion, "ভাত খাই")

    def test_non_bangla_completion_dropped(self):
        self.assertEqual(claude._clean({"words": [], "completion": "hello"}, 4).completion, "")

    def test_rejects_non_object(self):
        self.assertIsNone(claude._clean(["আমি"], 4))


if __name__ == "__main__":
    unittest.main()
