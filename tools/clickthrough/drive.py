"""Click-through of Table Reader's page in headless Edge (Chrome DevTools Protocol). Made-up data only.

python drive.py <scenario module>: runs that module's ``scenario(page, downloads)`` against the server on BASE (started
by run.sh). Each step prints what the page shows; a JavaScript error or a failed expectation is printed as PROBLEM."""
import asyncio
import json
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import websockets

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PORT = 9344
BASE = "http://127.0.0.1:8777"
problems: list[str] = []

HELPERS = r"""
window.confirm = () => true;
window.T = {
  sleep: (ms) => new Promise((r) => setTimeout(r, ms)),
  async until(fn, what, ms = 4000) {
    const end = Date.now() + ms;
    while (Date.now() < end) { try { if (fn()) return true; } catch (_) {} await T.sleep(50); }
    throw new Error("timed out waiting for: " + what);
  },
  set(id, value) {
    const n = document.getElementById(id);
    if (!n) throw new Error("no element #" + id);
    n.focus(); n.value = String(value);
    n.dispatchEvent(new Event("input", { bubbles: true })); n.dispatchEvent(new Event("change", { bubbles: true }));
  },
  button(text, root = document) {
    const b = [...root.querySelectorAll("button")].find((x) => x.textContent.trim() === text && !x.disabled && x.offsetParent !== null);
    if (!b) throw new Error("no button: " + text);
    return b;
  },
  click(text, root) { T.button(text, root).click(); },
  val: (id) => document.getElementById(id).value,
  text: (sel) => [...document.querySelectorAll(sel)].map((n) => n.textContent.trim()).join(" | "),
  howOf(id) { const n = document.getElementById(id); const row = n.closest(".pf") || n.closest("tr"); return row.querySelector(".why").textContent; },
  editFormula(id) { const n = document.getElementById(id); const row = n.closest(".pf") || n.closest("tr"); T.click("Edit formula", row); },
  saved: () => T.until(() => document.getElementById("em-save").textContent === "Saved", "Saved"),
};
"ok"
"""


class Page:
    def __init__(self, ws):
        self.ws, self.n, self.waiting = ws, 0, {}

    async def pump(self):
        async for raw in self.ws:
            msg = json.loads(raw)
            if "id" in msg and msg["id"] in self.waiting:
                self.waiting.pop(msg["id"]).set_result(msg)
            elif msg.get("method") == "Runtime.exceptionThrown":
                d = msg["params"]["exceptionDetails"]
                problems.append("JS exception: " + (d.get("exception", {}).get("description") or d.get("text", ""))[:300])
            elif msg.get("method") == "Runtime.consoleAPICalled" and msg["params"]["type"] in ("error", "warning"):
                problems.append("console " + msg["params"]["type"] + ": " + json.dumps(msg["params"]["args"])[:300])
            elif (msg.get("method") == "Log.entryAdded" and msg["params"]["entry"]["level"] == "error"
                  and not msg["params"]["entry"].get("url", "").endswith("/favicon.ico")):   # the app has no icon
                problems.append("log error: " + msg["params"]["entry"]["text"][:300] + " " + msg["params"]["entry"].get("url", ""))

    async def send(self, method, **params):
        self.n += 1
        fut = asyncio.get_running_loop().create_future()
        self.waiting[self.n] = fut
        await self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        return await asyncio.wait_for(fut, 30)

    async def ev(self, js):
        r = (await self.send("Runtime.evaluate", expression=js, awaitPromise=True, returnByValue=True))["result"]
        if "exceptionDetails" in r:
            d = r["exceptionDetails"]
            raise RuntimeError((d.get("exception", {}).get("description") or d.get("text", ""))[:400])
        return r["result"].get("value")

    async def goto(self, url):
        await self.send("Page.navigate", url="about:blank")
        await asyncio.sleep(0.3)
        await self.send("Page.navigate", url=url)
        for _ in range(100):                          # the page and its scripts loaded (up to 10 s)
            await asyncio.sleep(0.1)
            if await self.ev("document.readyState === 'complete' && location.href !== 'about:blank' && typeof route === 'function'"):
                break
        await asyncio.sleep(0.8)                      # its first requests
        await self.ev(HELPERS)


def expect(label, got, want):
    ok = got == want if not callable(want) else want(got)
    print(("  ok      " if ok else "  PROBLEM ") + f"{label}: {got!r}" + ("" if ok else f"   (wanted {want!r})" if not callable(want) else ""))
    if not ok:
        problems.append(f"{label}: got {got!r}")


async def run(scenario):
    profile = tempfile.mkdtemp(prefix="tr-edge-profile-")
    downloads = Path(tempfile.mkdtemp(prefix="tr-downloads-"))
    proc = subprocess.Popen([EDGE, "--headless=new", f"--remote-debugging-port={PORT}", f"--user-data-dir={profile}",
                             "--no-first-run", "--disable-gpu", "--window-size=1500,1000", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json"))
                break
            except OSError:
                time.sleep(0.25)
        target = next(t for t in tabs if t["type"] == "page")
        async with websockets.connect(target["webSocketDebuggerUrl"], max_size=None) as ws:
            page = Page(ws)
            pump = asyncio.create_task(page.pump())
            for domain in ("Runtime", "Page", "Log"):
                await page.send(domain + ".enable")
            await page.send("Emulation.setFocusEmulationEnabled", enabled=True)
            await page.send("Browser.setDownloadBehavior", behavior="allow", downloadPath=str(downloads))
            try:
                await scenario(page, downloads)
            except Exception as exc:  # noqa: BLE001
                problems.append(f"scenario stopped: {exc}")
                print("  PROBLEM scenario stopped:", exc)
                print("  page says:", (await page.ev("document.body.innerText"))[:1500])
            pump.cancel()
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            pass
        shutil.rmtree(profile, ignore_errors=True)
    print("\nPROBLEMS:" if problems else "\nNo problems.")
    for p in problems:
        print(" -", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    import importlib

    sys.path.insert(0, str(Path(__file__).parent))
    sys.modules["drive"] = sys.modules["__main__"]     # a scenario's "from drive import expect" adds to these problems
    sys.exit(asyncio.run(run(importlib.import_module(sys.argv[1]).scenario)))
