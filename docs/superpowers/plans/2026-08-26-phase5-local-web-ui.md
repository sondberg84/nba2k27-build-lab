# Phase 5: Local Web UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A browser page you open on your own machine with a height picker and twenty-one attribute sliders, showing overall, archetype, badges, animations and the threshold ladder updating as you drag.

**Architecture:** A `http.server` subclass serving three static files and a small JSON API over the existing engine. No framework, no build step, no CDN — the page is plain HTML, CSS and JavaScript, and the server is a hundred lines of standard library. The engine is imported directly, so the browser sees exactly the numbers the CLI does.

**Tech Stack:** Python 3.14 standard library only (`http.server`, `json`, `webbrowser`). Plain HTML/CSS/JS, no dependencies. `unittest` for tests.

---

## Context the implementer needs

Phases 1a through 4 are merged. 293 tests pass. Available modules:

- `buildlab.sources` — `path_for`, `rows_for`, `verify()`, `verify_all()`, `parse_manifest`, `load()`, `SourceError`, `ROOT`
- `buildlab.reference` — `attribute_names()` (21 snake_case, builder index order), `TUNING_NAME`, `legal_bodies()`
- `buildlab.body` — `is_legal(position, height, weight, wingspan)`, `ceilings(height, weight, wingspan)`
- `buildlab.ovr` — `overall(height_inches, values)`, `detailed(...)`, `archetype(...)`
- `buildlab.badges` — `TIERS`, `by_id`, `by_name`, `unlocked(values, height_inches)`, `best_tier`
- `buildlab.tokens` — `cost_for`, `has_token_data(height)`, `TOKEN_DATA_HEIGHTS`, `earned(values, height)`
- `buildlab.animations` — `available(values, height_inches, family=None)`, `families()`, `max_ceiling_at(height_inches, attribute)`, `reachable_range`
- `buildlab.ladders` — `ATTRIBUTE_FLOOR` (25), `ladder(attribute, height_inches)`, `dead_points(attribute, height_inches, rating)`, `max_ceiling`, `full_cost_of`
- `buildlab.goals`, `buildlab.solver`, `buildlab.critique`, `buildlab.refresh`, `buildlab.ratings`
- `buildlab.cli` — `main(argv)`, `parse_height(text)`, `_ft(inches)`, subcommands `eval`, `badges`, `animations`, `ladder`, `reachability`, `solve`, `critique`, `refresh`, `rate`

Codebase idioms: `@functools.lru_cache` loaders, `KeyError` messages naming inputs and valid ranges, and **refuse rather than guess** (`docs/superpowers/notes/error-conventions.md`).

### The one carried note this phase must close

From the phase 1b review, tagged for whichever plan first introduces a long-running process:

> **`lru_cache(maxsize=1)` on `sources.load()` is a staleness hazard in a long-running process.** Fine for short-lived CLI runs. A resident server that stays up while somebody re-runs `tools/vendor.py` would keep serving the old manifest, and `verify()` would validate against stale in-memory state.

**This is that process.** The honest resolution here is not cache invalidation but an explicit contract: the server verifies every hash at startup, states that it holds the data for the life of the process, and tells you to restart it after a data change. Add a `/api/health` endpoint reporting the pinned commit so the page can show what it is serving.

### Things that will bite you

1. **Never bind to anything but localhost.** This is a personal tool holding nothing sensitive, but a server that listens on `0.0.0.0` by default is a bad habit and an unwelcome surprise on a shared network. Bind `127.0.0.1`.
2. **`tokens.earned` raises for heights 82-88.** The API must catch that and report tokens as unavailable rather than 500ing. A centre is a completely normal thing to look at.
3. **`ladders.ladder` is `lru_cache`d and returns tuples inside dicts.** Do not mutate what it returns; serialise a copy.
4. **`animations.max_ceiling_at` scans every legal weight and wingspan on first call per (height, attribute).** Warm at startup for the default height or the first slider drag will stutter.
5. **No CDN, no framework, no build step.** Plain files. The whole point is that this runs with nothing installed.

---

## File structure

| File | Responsibility |
|---|---|
| `buildlab/api.py` | Pure functions returning JSON-ready dicts for each view |
| `buildlab/server.py` | The `http.server` handler, routing and static file serving |
| `ui/index.html` | The page |
| `ui/style.css` | Styling |
| `ui/app.js` | Slider handling and fetch calls |
| `buildlab/cli.py` | Add a `serve` subcommand (modify) |
| `tests/test_api.py` | The API shapes, without a socket |
| `tests/test_server.py` | Routing and static serving, on an ephemeral port |
| `tests/test_cli.py` | Coverage for `serve` argument handling (modify) |

`api.py` depends on the engine modules and nothing else — it is testable without a socket, which is where the real coverage goes. `server.py` is thin on purpose.

---

## Task 1: The API layer

**Files:**
- Create: `buildlab/api.py`
- Create: `tests/test_api.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_api.py`:

```python
import json
import unittest

from buildlab import api


class TestMeta(unittest.TestCase):
    def test_meta_lists_the_attributes_in_order(self):
        payload = api.meta()
        self.assertEqual(len(payload["attributes"]), 21)
        self.assertEqual(payload["attributes"][0], "close_shot")
        self.assertEqual(payload["attributes"][20], "vertical")

    def test_meta_gives_the_legal_height_range(self):
        payload = api.meta()
        self.assertEqual(payload["min_height"], 69)
        self.assertEqual(payload["max_height"], 88)

    def test_meta_reports_the_pinned_commit(self):
        payload = api.meta()
        self.assertEqual(len(payload["commit"]), 40)

    def test_meta_gives_the_attribute_floor(self):
        self.assertEqual(api.meta()["floor"], 25)

    def test_meta_is_json_serialisable(self):
        json.dumps(api.meta())


class TestEvaluate(unittest.TestCase):
    def setUp(self):
        self.values = [70] * 21

    def test_evaluate_returns_overall_and_archetype(self):
        payload = api.evaluate(self.values, 76)
        self.assertIn("overall", payload)
        self.assertIn("archetype", payload)

    def test_evaluate_matches_the_engine(self):
        from buildlab import ovr

        payload = api.evaluate(self.values, 76)
        self.assertEqual(payload["overall"], ovr.overall(76, self.values))

    def test_evaluate_counts_badges_and_animations(self):
        payload = api.evaluate(self.values, 76)
        self.assertGreaterEqual(payload["badge_count"], 0)
        self.assertGreater(payload["animation_count"], 0)

    def test_evaluate_reports_ceilings(self):
        payload = api.evaluate(self.values, 76)
        self.assertEqual(len(payload["ceilings"]), 21)

    def test_evaluate_flags_values_above_the_ceiling(self):
        values = [70] * 21
        values[3] = 95
        payload = api.evaluate(values, 76)
        self.assertTrue(payload["illegal"])

    def test_evaluate_reports_tokens_when_available(self):
        payload = api.evaluate(self.values, 76)
        self.assertTrue(payload["tokens"]["available"])
        self.assertIn("total", payload["tokens"])

    def test_evaluate_degrades_where_token_data_is_missing(self):
        # 84 inches is inside the range where every token value is zero in the
        # shipped data. It must report unavailable, never zero.
        payload = api.evaluate(self.values, 84)
        self.assertFalse(payload["tokens"]["available"])
        self.assertIn("reason", payload["tokens"])

    def test_evaluate_rejects_a_wrong_length_vector(self):
        with self.assertRaises(ValueError):
            api.evaluate([70] * 20, 76)

    def test_evaluate_rejects_an_illegal_height(self):
        with self.assertRaises(ValueError):
            api.evaluate(self.values, 60)

    def test_evaluate_is_json_serialisable(self):
        json.dumps(api.evaluate(self.values, 76))


class TestLadder(unittest.TestCase):
    def test_ladder_returns_steps(self):
        payload = api.ladder("ball_handle", 76)
        self.assertGreater(len(payload["steps"]), 0)
        self.assertIn("ceiling", payload)

    def test_ladder_steps_are_plain_lists(self):
        payload = api.ladder("ball_handle", 76)
        for step in payload["steps"]:
            self.assertIsInstance(step["badges"], list)
            self.assertIsInstance(step["animations"], list)

    def test_ladder_rejects_an_unknown_attribute(self):
        with self.assertRaises(KeyError):
            api.ladder("nonsense", 76)

    def test_ladder_is_json_serialisable(self):
        json.dumps(api.ladder("ball_handle", 76))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_api -v`
Expected: FAIL with `ImportError: cannot import name 'api'`

- [ ] **Step 3: Write the implementation**

Create `buildlab/api.py`:

```python
"""JSON-ready views over the engine, for the local web UI.

Pure functions returning plain dicts. No sockets here — that is server.py —
so all of this is testable directly.
"""

from buildlab import (
    animations,
    badges,
    ladders,
    ovr,
    reference,
    solver,
    sources,
    tokens,
)


def meta():
    """Everything the page needs before it can render anything."""
    return {
        "attributes": list(reference.attribute_names()),
        "min_height": solver.MIN_HEIGHT,
        "max_height": solver.MAX_HEIGHT,
        "floor": ladders.ATTRIBUTE_FLOOR,
        "commit": sources.load()["sources"][0]["commit"],
        "families": list(animations.families()),
    }


def _check(values, height_inches):
    if len(values) != 21:
        raise ValueError(f"expected 21 attribute values, got {len(values)}")
    if not solver.MIN_HEIGHT <= height_inches <= solver.MAX_HEIGHT:
        raise ValueError(
            f"height {height_inches} is outside the legal range "
            f"{solver.MIN_HEIGHT}-{solver.MAX_HEIGHT}"
        )


def evaluate(values, height_inches):
    """The main view: everything that changes as you drag a slider."""
    _check(values, height_inches)
    names = reference.attribute_names()

    ceilings = {
        name: animations.max_ceiling_at(height_inches, name) for name in names
    }
    illegal = [
        {"attribute": name, "value": values[i], "ceiling": ceilings[name]}
        for i, name in enumerate(names)
        if values[i] > ceilings[name]
    ]

    unlocked = badges.unlocked(values, height_inches)
    by_tier = {tier: [] for tier in badges.TIERS}
    for badge_id, tier in unlocked.items():
        by_tier[tier].append(badges.by_id(badge_id)["name"])
    for tier in by_tier:
        by_tier[tier].sort()

    if tokens.has_token_data(height_inches):
        earned = tokens.earned(values, height_inches)
        token_view = {
            "available": True,
            "total": earned["total"],
            "per_discipline": list(earned["per_discipline"]),
            "locally_verified": earned["locally_verified"],
        }
    else:
        low = tokens.TOKEN_DATA_HEIGHTS[0]
        high = tokens.TOKEN_DATA_HEIGHTS[-1]
        token_view = {
            "available": False,
            "reason": (
                f"The shipped data records zero tokens for every attribute at "
                f"height {height_inches}, while badge slots stay populated. "
                f"That reads as a capture gap, not a game rule, so it is "
                f"treated as missing rather than as zero. Trustworthy heights "
                f"are {low}-{high} inches."
            ),
        }

    return {
        "height_inches": height_inches,
        "overall": ovr.overall(height_inches, values),
        "detailed": round(ovr.detailed(height_inches, values), 4),
        "archetype": ovr.archetype(height_inches, values),
        "badge_count": len(unlocked),
        "badges_by_tier": by_tier,
        "animation_count": len(animations.available(values, height_inches)),
        "ceilings": ceilings,
        "illegal": illegal,
        "points": sum(max(v - ladders.ATTRIBUTE_FLOOR, 0) for v in values),
        "tokens": token_view,
    }


def ladder(attribute, height_inches):
    """The threshold ladder for one attribute, as plain lists."""
    steps = ladders.ladder(attribute, height_inches)
    return {
        "attribute": attribute,
        "height_inches": height_inches,
        "ceiling": ladders.max_ceiling(attribute, height_inches),
        "steps": [
            {
                "rating": step["rating"],
                "badges": list(step["badges"]),
                "animations": list(step["animations"]),
            }
            for step in steps
        ],
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_api -v`
Expected: `OK`, 19 tests

Then the full suite: `python -m unittest discover -s tests -v`
Expected: 312 tests, OK.

- [ ] **Step 5: Commit**

```bash
git add buildlab/api.py tests/test_api.py && git commit -m "feat: JSON views over the engine for a local UI"
```

---

## Task 2: The server

> **Do Task 3 first.** The server's tests check that `index.html`, `style.css` and
> `app.js` are served, so they cannot pass until those files exist. Create the page
> (Task 3), then come back here. Written in this order because the server's shape is
> easier to read before the markup, but the build order is the reverse.

**Files:**
- Create: `buildlab/server.py`
- Create: `tests/test_server.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_server.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_server -v`
Expected: FAIL with `ImportError: cannot import name 'server'`

- [ ] **Step 3: Write the implementation**

Create `buildlab/server.py`:

```python
"""A local-only HTTP server for the build UI.

Binds 127.0.0.1 and nothing else. The engine's data is loaded once and held for
the life of the process, so after re-running tools/vendor.py you must restart
the server — /api/health reports which commit is being served.
"""

import http.server
import json
import pathlib

from buildlab import api, sources

UI = sources.ROOT / "ui"

STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "buildlab"

    def log_message(self, format, *args):
        """Quiet by default; the test suite should not print a request log."""

    def _send(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status, payload):
        self._send(
            status,
            json.dumps(payload).encode("utf-8"),
            "application/json; charset=utf-8",
        )

    def do_GET(self):
        if self.path == "/api/health":
            problems = sources.verify_all()
            self._send_json(
                200,
                {
                    "commit": sources.load()["sources"][0]["commit"],
                    "hashes_ok": not problems,
                    "problems": problems,
                },
            )
            return
        if self.path == "/api/meta":
            self._send_json(200, api.meta())
            return
        if self.path in STATIC:
            name, content_type = STATIC[self.path]
            path = UI / name
            if not path.exists():
                self._send_json(404, {"error": f"missing {name}"})
                return
            self._send(200, path.read_bytes(), content_type)
            return
        self._send_json(404, {"error": f"no such path {self.path}"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError as error:
            self._send_json(400, {"error": f"invalid JSON: {error}"})
            return

        try:
            if self.path == "/api/evaluate":
                result = api.evaluate(payload["values"], int(payload["height"]))
            elif self.path == "/api/ladder":
                result = api.ladder(payload["attribute"], int(payload["height"]))
            else:
                self._send_json(404, {"error": f"no such path {self.path}"})
                return
        except (ValueError, KeyError) as error:
            self._send_json(400, {"error": str(error).strip("'")})
            return

        self._send_json(200, result)


def build(port=8765):
    """An HTTP server bound to localhost. Pass port=0 for an ephemeral one."""
    return http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)


def warm():
    """Precompute the slow lookups so the first slider drag is not sluggish."""
    api.meta()
    api.evaluate([25] * 21, 75)
```

Note the traversal test: paths like `/../buildlab/ovr.py` are normalised by the client or simply do not appear in `STATIC`, so they fall through to the 404 branch. There is no filesystem path built from user input anywhere — `STATIC` is a fixed allowlist. That is the actual defence and it is stronger than sanitising.

- [ ] **Step 4: Run test to verify it passes**

With Task 3's page already in place:

Run: `python -m unittest tests.test_server -v`
Expected: `OK`, 10 tests

Then the full suite: `python -m unittest discover -s tests -v`
Expected: 322 tests, OK.

- [ ] **Step 5: Commit**

```bash
git add buildlab/server.py tests/test_server.py && git commit -m "feat: a localhost-only server for the build UI"
```

---

## Task 3: The page

**Files:**
- Create: `ui/index.html`
- Create: `ui/style.css`
- Create: `ui/app.js`

- [ ] **Step 1: Create `ui/index.html`**

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>2K27 Build Lab</title>
<link rel="stylesheet" href="/style.css">
</head>
<body>
<header>
  <h1>2K27 Build Lab</h1>
  <p class="pin">data pinned at <span id="commit">…</span></p>
</header>

<section class="summary">
  <div class="stat"><span class="label">overall</span><span class="value" id="overall">—</span></div>
  <div class="stat"><span class="label">archetype</span><span class="value" id="archetype">—</span></div>
  <div class="stat"><span class="label">badges</span><span class="value" id="badges">—</span></div>
  <div class="stat"><span class="label">animations</span><span class="value" id="animations">—</span></div>
  <div class="stat"><span class="label">upgrades</span><span class="value" id="points">—</span></div>
  <div class="stat"><span class="label">tokens</span><span class="value" id="tokens">—</span></div>
</section>

<p class="warn" id="warn" hidden></p>

<section class="height">
  <label for="height">height <output id="heightOut">6-3</output></label>
  <input type="range" id="height" min="69" max="88" value="75">
</section>

<main>
  <section class="sliders" id="sliders"></section>
  <aside class="ladder">
    <h2>ladder <span id="ladderAttr">ball_handle</span></h2>
    <p class="hint">click an attribute name to see what each point buys</p>
    <ol id="ladderSteps"></ol>
  </aside>
</main>

<script src="/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Create `ui/style.css`**

```css
:root {
  --bg: #14161a;
  --panel: #1c1f25;
  --line: #2b303a;
  --text: #e7e9ee;
  --dim: #949bab;
  --accent: #4da3ff;
  --bad: #ff6b6b;
}
* { box-sizing: border-box; }
body {
  margin: 0; padding: 1.5rem;
  background: var(--bg); color: var(--text);
  font: 15px/1.5 ui-sans-serif, system-ui, -apple-system, sans-serif;
}
h1 { font-size: 1.25rem; margin: 0; }
header { display: flex; align-items: baseline; gap: 1rem; margin-bottom: 1rem; }
.pin { color: var(--dim); font-size: 0.8rem; margin: 0; }

.summary { display: flex; flex-wrap: wrap; gap: 0.75rem; margin-bottom: 1rem; }
.stat {
  background: var(--panel); border: 1px solid var(--line); border-radius: 8px;
  padding: 0.6rem 0.9rem; min-width: 7rem;
}
.stat .label { display: block; color: var(--dim); font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.06em; }
.stat .value { display: block; font-size: 1.4rem; font-variant-numeric: tabular-nums; }

.warn {
  background: #3a2226; border: 1px solid var(--bad); color: #ffd7d7;
  padding: 0.6rem 0.9rem; border-radius: 8px; margin: 0 0 1rem;
}

.height { margin-bottom: 1.25rem; }
.height label { display: block; color: var(--dim); font-size: 0.8rem; margin-bottom: 0.25rem; }
.height output { color: var(--text); font-size: 1rem; font-variant-numeric: tabular-nums; }
.height input { width: 100%; }

main { display: grid; grid-template-columns: 1fr 22rem; gap: 1.5rem; align-items: start; }
@media (max-width: 900px) { main { grid-template-columns: 1fr; } }

.row { display: grid; grid-template-columns: 11rem 1fr 3rem; gap: 0.6rem; align-items: center; padding: 0.15rem 0; }
.row button {
  background: none; border: none; color: var(--dim); font: inherit;
  text-align: left; cursor: pointer; padding: 0;
}
.row button:hover, .row button.on { color: var(--accent); }
.row input { width: 100%; }
.row .num { text-align: right; font-variant-numeric: tabular-nums; }
.row.over .num { color: var(--bad); font-weight: 600; }

.ladder { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 1rem; }
.ladder h2 { font-size: 0.95rem; margin: 0 0 0.25rem; }
.ladder .hint { color: var(--dim); font-size: 0.75rem; margin: 0 0 0.75rem; }
.ladder ol { list-style: none; margin: 0; padding: 0; }
.ladder li { display: grid; grid-template-columns: 2.5rem 1fr; gap: 0.5rem; padding: 0.2rem 0; border-top: 1px solid var(--line); }
.ladder li .r { color: var(--accent); font-variant-numeric: tabular-nums; }
.ladder li .u { color: var(--dim); font-size: 0.8rem; }
.ladder li.gap { color: var(--dim); font-size: 0.75rem; font-style: italic; grid-template-columns: 1fr; }
```

- [ ] **Step 3: Create `ui/app.js`**

```javascript
const state = { meta: null, height: 75, values: [], focus: "ball_handle" };

const $ = (id) => document.getElementById(id);
const ft = (inches) => `${Math.floor(inches / 12)}-${inches % 12}`;

async function post(path, body) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error((await response.json()).error);
  return response.json();
}

function buildSliders() {
  const host = $("sliders");
  host.innerHTML = "";
  state.meta.attributes.forEach((name, index) => {
    const row = document.createElement("div");
    row.className = "row";
    row.id = `row-${name}`;

    const label = document.createElement("button");
    label.textContent = name;
    label.onclick = () => { state.focus = name; refreshLadder(); markFocus(); };

    const slider = document.createElement("input");
    slider.type = "range";
    slider.min = state.meta.floor;
    slider.max = 99;
    slider.value = state.values[index];
    slider.oninput = () => {
      state.values[index] = Number(slider.value);
      row.querySelector(".num").textContent = slider.value;
      refreshEvaluate();
    };

    const num = document.createElement("span");
    num.className = "num";
    num.textContent = state.values[index];

    row.append(label, slider, num);
    host.append(row);
  });
  markFocus();
}

function markFocus() {
  document.querySelectorAll(".row button").forEach((b) => {
    b.classList.toggle("on", b.textContent === state.focus);
  });
  $("ladderAttr").textContent = state.focus;
}

async function refreshEvaluate() {
  let data;
  try {
    data = await post("/api/evaluate", { height: state.height, values: state.values });
  } catch (error) {
    $("warn").hidden = false;
    $("warn").textContent = error.message;
    return;
  }
  $("overall").textContent = data.overall;
  $("archetype").textContent = data.archetype;
  $("badges").textContent = data.badge_count;
  $("animations").textContent = data.animation_count;
  $("points").textContent = data.points;
  $("tokens").textContent = data.tokens.available ? data.tokens.total : "n/a";

  state.meta.attributes.forEach((name) => {
    const row = $(`row-${name}`);
    if (row) row.classList.remove("over");
  });
  data.illegal.forEach((entry) => {
    const row = $(`row-${entry.attribute}`);
    if (row) row.classList.add("over");
  });

  const messages = [];
  if (data.illegal.length) {
    messages.push(
      data.illegal
        .map((e) => `${e.attribute} ${e.value} is above its ceiling of ${e.ceiling}`)
        .join("; ")
    );
  }
  if (!data.tokens.available) messages.push(data.tokens.reason);
  $("warn").hidden = messages.length === 0;
  $("warn").textContent = messages.join("  ·  ");
}

async function refreshLadder() {
  const data = await post("/api/ladder", {
    height: state.height,
    attribute: state.focus,
  });
  const list = $("ladderSteps");
  list.innerHTML = "";
  let previous = null;
  data.steps.forEach((step) => {
    if (previous !== null && step.rating - previous > 1) {
      const gap = document.createElement("li");
      gap.className = "gap";
      const n = step.rating - previous - 1;
      gap.textContent = `${n} point${n > 1 ? "s" : ""} buying nothing`;
      list.append(gap);
    }
    const unlocks = step.badges.concat(step.animations);
    const item = document.createElement("li");
    const rating = document.createElement("span");
    rating.className = "r";
    rating.textContent = step.rating;
    const text = document.createElement("span");
    text.className = "u";
    text.textContent =
      unlocks.length > 3 ? `${unlocks[0]} (+${unlocks.length - 1} more)` : unlocks.join(", ");
    item.append(rating, text);
    list.append(item);
    previous = step.rating;
  });
}

async function start() {
  state.meta = await (await fetch("/api/meta")).json();
  state.values = new Array(state.meta.attributes.length).fill(state.meta.floor);
  $("commit").textContent = state.meta.commit.slice(0, 12);

  const height = $("height");
  height.min = state.meta.min_height;
  height.max = state.meta.max_height;
  height.value = state.height;
  $("heightOut").textContent = ft(state.height);
  height.oninput = () => {
    state.height = Number(height.value);
    $("heightOut").textContent = ft(state.height);
    refreshEvaluate();
    refreshLadder();
  };

  buildSliders();
  await refreshEvaluate();
  await refreshLadder();
}

start();
```

- [ ] **Step 4: Commit**

The page has no tests of its own — it is exercised through the server in Task 2. Commit it,
then go back and do Task 2.

```bash
git add ui && git commit -m "feat: the build lab page"
```

---

## Task 4: The `serve` command

**Files:**
- Modify: `buildlab/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli.py`, before the `if __name__` block:

```python
class TestServeCommand(unittest.TestCase):
    def test_serve_rejects_a_bad_port(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = cli.main(["serve", "--port", "99999"])
        self.assertEqual(code, 2)
        self.assertIn("port", buffer.getvalue().lower())

    def test_serve_is_a_registered_command(self):
        # Argparse should know about it without starting a server.
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            with self.assertRaises(SystemExit):
                cli.main(["--help"])
        self.assertIn("serve", buffer.getvalue())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_cli -v`
Expected: FAIL — `argparse` rejects `serve`

- [ ] **Step 3: Write the implementation**

Add `server as server_mod` to the `cli.py` import block.

Add after `_rate`:

```python
def _serve(args):
    if not 1 <= args.port <= 65535:
        print(f"error: port {args.port} is outside the valid range 1-65535")
        return 2

    problems = sources.verify_all()
    if problems:
        print(f"error: {len(problems)} data files do not match the manifest")
        for problem in problems:
            print(f"  {problem}")
        return 2

    print("warming the engine…")
    server_mod.warm()
    httpd = server_mod.build(port=args.port)
    host, port = httpd.server_address
    print(f"BUILD LAB  http://{host}:{port}")
    print()
    print("  Data is held for the life of this process. If you re-run")
    print("  tools/vendor.py, restart the server so it picks up the change.")
    print("  Ctrl-C to stop.")
    if not args.no_browser:
        webbrowser.open(f"http://{host}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print()
        print("stopped")
    finally:
        httpd.server_close()
    return 0
```

Add `import webbrowser` and `from buildlab import sources` at the top of `cli.py` if they are not already there — check before adding, several modules are already imported.

Register in `main`, before `args = parser.parse_args(argv)`:

```python
    sr = sub.add_parser("serve", help="open the build lab in your browser")
    sr.add_argument("--port", type=int, default=8765, help="default 8765")
    sr.add_argument(
        "--no-browser", action="store_true", help="do not open a browser"
    )
    sr.set_defaults(func=_serve)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_cli -v`
Expected: `OK`, 34 tests

Then the full suite: `python -m unittest discover -s tests -v`
Expected: 324 tests, OK.

- [ ] **Step 5: Try it by hand**

```bash
python -m buildlab.cli serve --no-browser
```

Then in another terminal:

```bash
curl -s http://127.0.0.1:8765/api/health
```

Confirm it returns the pinned commit and `"hashes_ok": true`, then stop the server with Ctrl-C. Report the health output.

- [ ] **Step 6: Commit**

```bash
git add buildlab/cli.py tests/test_cli.py && git commit -m "feat: add the serve subcommand"
```

---

## Definition of done

- `python -m unittest discover -s tests` passes with no failures and no skips.
- `python -m buildlab.cli serve` opens a working page with a height picker, 21 sliders, live overall/archetype/badge/animation counts and a ladder.
- The server binds `127.0.0.1` and nothing else.
- A value above its ceiling turns red and raises a warning rather than silently reporting a number.
- A height of 6'10" or taller shows tokens as unavailable with the reason, not as zero.
- `/api/health` reports the pinned commit and whether the hashes still match.
- No CDN, no framework, no build step, no third-party imports anywhere.

## Explicitly not in this plan

Saving and comparing builds, the solver and critique views, and editing ratings from the browser. The page is a live readout, not a workspace — those are worth doing once it has been used enough to know what the layout should be.
