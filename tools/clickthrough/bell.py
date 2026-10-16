"""Step 3's bell: what opening the month did by itself becomes one short message (a toast, a number on the bell),
nothing sits above the list; opening the list marks it read; it stays when another employee opens; its × removes it;
with the tab's storage refused the bell still works."""
from drive import BASE, expect

M = "2026-09"
NOTE = ('[{"added": {"added": [{"name": "AMIN", "cards": 1}], "joined": [], "skipped": [], "unnamed": [], "no_month": [], '
        '"from_million": 0, "new_numbers": 1}, "numbered": 0}]')


async def scenario(page, downloads):
    await page.goto(f"{BASE}/#/check")
    await page.ev("T.until(() => /^#\\/check\\/./.test(location.hash) && !document.getElementById('doc').hidden, 'step 2', 6000)")
    people = await page.ev(f"fetch('/api/payroll/{M}/people').then((r) => r.json())")
    ids = {(r["company"], e["name"]): e["id"] for r in people["companies"] for e in r["employees"]}
    siti = ids[("MAJU JAYA", "SITI")]
    await page.ev(f"sessionStorage.setItem('notes.{M}', {NOTE!r}); location.hash = '#/payroll/{M}'")
    await page.ev("T.until(() => T.text('#bell-count') === '1', 'one unread', 6000)")
    expect("no banner above the list", await page.ev("document.getElementById('mo-info') === null"), True)
    expect("toast", "AMIN" in await page.ev("document.getElementById('bell-toast').textContent"), True)
    await page.ev("T.click('Messages')")
    await page.ev("T.until(() => !document.getElementById('bell-list').hidden, 'list')")
    expect("short line", await page.ev("document.querySelector('#bell-list .msg-line').textContent"),
           "AMIN added · 1 card · 1 new Employee No.")
    expect("the long text folded", await page.ev("!document.querySelector('#bell-list .msg details').open"), True)
    expect("read: count gone", await page.ev("document.getElementById('bell-count').hidden"), True)
    # another employee: the message stays in the bell
    await page.ev(f"location.hash = '#/payroll/{M}/e/{siti}'")
    await page.ev("T.until(() => document.getElementById('em-title').textContent.includes('SITI'), 'SITI', 6000)")
    expect("kept", await page.ev("document.querySelectorAll('#bell-list .msg').length"), 1)
    await page.ev("document.querySelector('#bell-list .msg .icon-btn[title=\"Close\"]').click()")
    expect("× removes it", await page.ev("document.querySelectorAll('#bell-list .msg').length"), 0)
    # a file without a month is in the server's note on every load until a month is chosen: said once, not on each
    # refresh (and not again after its × either)
    await page.ev("window._api = api; api = async (m, u, b) => { const r = await _api(m, u, b); if (/\\/people$/.test(u)) "
                  "r.added_by_themselves = { added: [], joined: [], skipped: [], unnamed: [], from_million: 0, new_numbers: 0, "
                  "no_month: [{ name: 'card.jpg', why: 'no date' }] }; return r; }")
    await page.ev("ppLoad().then(() => ppLoad()).then(() => ppLoad())")
    await page.ev("T.until(() => document.querySelectorAll('#bell-list .msg').length > 0, 'the note', 4000)")
    expect("said once", await page.ev("document.querySelectorAll('#bell-list .msg').length"), 1)
    await page.ev("document.querySelector('#bell-list .msg .icon-btn[title=\"Close\"]').click()")
    await page.ev("ppLoad().then(() => ppLoad())")
    expect("not said again after ×", await page.ev("document.querySelectorAll('#bell-list .msg').length"), 0)
    await page.ev("api = window._api")
    # storage refused (Review Focus 3): still shown in this visit
    await page.ev("Storage.prototype.setItem = () => { throw new Error('refused'); }")
    await page.ev(f"bellAdd('{M}', {{ icon: 'users', line: 'Employee list imported', detail: '' }})")
    expect("still counted", await page.ev("T.text('#bell-count')"), "1")
    expect("still listed", "Employee list imported" in await page.ev("T.text('#bell-list .msg-line')"), True)
