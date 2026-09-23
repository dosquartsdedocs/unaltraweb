"""Opt-in browser regression against a locally served editorial-review page.

Set UNALTRAWEB_BROWSER_TEST_URL to the local page URL and install Chromium and
websocket-client. The ordinary offline suite skips this browser-only check.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
URL = os.environ.get("UNALTRAWEB_BROWSER_TEST_URL", "")
CHROMIUM = shutil.which("chromium") or shutil.which("google-chrome")


@unittest.skipUnless(URL and CHROMIUM and importlib.util.find_spec("websocket"), "Local browser review URL, Chromium and websocket-client are required")
class CodeBlockLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import websocket

        parsed = urllib.parse.urlsplit(URL)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"} or parsed.username or parsed.password:
            raise ValueError("Use a local HTTP review URL.")
        (ROOT / "tmp").mkdir(exist_ok=True)
        cls.profile = tempfile.TemporaryDirectory(prefix="code-layout-browser-", dir=ROOT / "tmp")
        cls.addClassCleanup(cls.profile.cleanup)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        cls.connection = None
        cls.serial = 0
        cls.browser = subprocess.Popen([
            CHROMIUM, "--headless", "--disable-gpu", "--disable-dev-shm-usage",
            "--no-first-run", "--no-default-browser-check", f"--user-data-dir={cls.profile.name}",
            f"--remote-debugging-port={port}", "about:blank",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.addClassCleanup(cls.close_browser)
        for attempt in range(150):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=1) as response:
                    page = next(item for item in json.load(response) if item["type"] == "page" and item["url"] == "about:blank")
                break
            except (OSError, StopIteration):
                time.sleep(.2)
        else:
            raise RuntimeError("Isolated Chromium did not become ready.")
        cls.connection = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=20, suppress_origin=True)
        cls.cdp("Page.enable")
        cls.cdp("Page.navigate", url=URL)
        for attempt in range(150):
            ready = cls.evaluate('''(() => {
              const block = document.querySelector('.uw-code-block[data-code-language="json"]');
              return block && getComputedStyle(block).overflow === 'hidden';
            })()''')
            if ready:
                break
            time.sleep(.2)
        else:
            raise RuntimeError("The local review page and compiled code styles did not load.")
        cls.evaluate('''window.codeLayoutSamples = ['yaml', 'json'].map(language =>
          document.querySelector(`.uw-code-block[data-code-language="${language}"]`).outerHTML)''')

    @classmethod
    def close_browser(cls):
        if cls.connection:
            try:
                cls.cdp("Browser.close")
            except Exception:
                pass
            cls.connection.close()
        cls.browser.wait(timeout=15)

    @classmethod
    def cdp(cls, method, **params):
        cls.serial += 1
        cls.connection.send(json.dumps({"id": cls.serial, "method": method, "params": params}))
        while True:
            result = json.loads(cls.connection.recv())
            if result.get("id") == cls.serial:
                if "error" in result:
                    raise RuntimeError(result["error"])
                return result.get("result", {})

    @classmethod
    def evaluate(cls, expression):
        result = cls.cdp("Runtime.evaluate", expression=expression, returnByValue=True)
        if "exceptionDetails" in result:
            raise RuntimeError(result["exceptionDetails"])
        return result["result"].get("value")

    def test_code_lines_keep_their_gutter_alignment_and_intentional_blank_lines(self):
        for profile, content_class in (("unaltredocs", "documentation-content"), ("unaltremanual", "manual-content")):
            for width in (1280, 390):
                with self.subTest(profile=profile, width=width):
                    self.cdp("Emulation.setDeviceMetricsOverride", width=width, height=1000, deviceScaleFactor=1, mobile=width == 390)
                    self.evaluate(f'''(() => {{
                      document.body.className = 'site-profile-{profile}';
                      document.body.innerHTML = '<main class="container" role="main"><article class="{content_class}"></article></main>';
                      const article = document.querySelector('article');
                      article.innerHTML = window.codeLayoutSamples.join('');
                      const blank = article.firstElementChild.cloneNode(true);
                      blank.querySelector('code').textContent = 'root:\\n\\n  child: value\\n';
                      blank.querySelector('.lineno').textContent = '1\\n2\\n3\\n';
                      blank.dataset.codeLanguage = 'intentional-blank';
                      article.append(blank);
                    }})()''')
                    result = self.evaluate(r'''(() => {
                      function starts(element) {
                        const text = element.textContent.replace(/\n$/, '');
                        const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
                        const nodes = []; let offset = 0; let node;
                        while ((node = walker.nextNode())) {
                          nodes.push({node, start: offset}); offset += node.textContent.length;
                        }
                        offset = 0;
                        return text.split('\n').map(line => {
                          const first = line.search(/\S/); const index = offset + first;
                          offset += line.length + 1;
                          if (first < 0) return null;
                          const found = nodes.find(item => index >= item.start && index < item.start + item.node.textContent.length);
                          const range = document.createRange();
                          range.setStart(found.node, index - found.start);
                          range.setEnd(found.node, index - found.start + 1);
                          const bounds = range.getBoundingClientRect();
                          return {x: bounds.x, y: bounds.y};
                        });
                      }
                      return {overflow: document.documentElement.scrollWidth > window.innerWidth,
                        blocks: [...document.querySelectorAll('.uw-code-block')].map(block => {
                          const code = block.querySelector('code'); const gutter = block.querySelector('.lineno');
                          return {language: block.dataset.codeLanguage, whiteSpace: getComputedStyle(code).whiteSpace,
                            text: code.textContent, codeRows: starts(code), numbers: starts(gutter),
                            codeHeight: code.parentElement.getBoundingClientRect().height,
                            gutterHeight: gutter.getBoundingClientRect().height};
                        })};
                    })()''')
                    self.assertFalse(result["overflow"], result)
                    for block in result["blocks"]:
                        self.assertEqual(block["whiteSpace"], "pre", block)
                        self.assertEqual(len(block["codeRows"]), len(block["numbers"]), block)
                        self.assertAlmostEqual(block["codeHeight"], block["gutterHeight"], delta=1, msg=str(block))
                        for code, number in zip(block["codeRows"], block["numbers"]):
                            if code:
                                self.assertAlmostEqual(code["y"], number["y"], delta=1, msg=str(block))
                        if block["language"] == "intentional-blank":
                            self.assertEqual(block["text"], "root:\n\n  child: value\n")
                            self.assertIsNone(block["codeRows"][1])
                            self.assertGreater(block["codeRows"][2]["x"], block["codeRows"][0]["x"] + 8)


if __name__ == "__main__":
    unittest.main()
