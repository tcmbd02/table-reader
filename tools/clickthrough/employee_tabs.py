"""Step 3's employee in tabs (run with YELLOW_FILE=1: MEI's card has a yellow cell, so MEI has something to fix):
To fix · Cards · Hours · Pay; an employee with something to fix opens on To fix, another on the tab chosen last; the
items' long sentences are folded; card actions are icons (Move to in a pop-up); Remove employee is in the More menu."""
from drive import BASE, expect

M = "2026-09"


async def scenario(page, downloads):
    await page.goto(f"{BASE}/")
    people = await page.ev(f"fetch('/api/payroll/{M}/people').then((r) => r.json())")
    ids = {(r["company"], e["name"]): e["id"] for r in people["companies"] for e in r["employees"]}
    mei, siti = ids[("MAJU JAYA", "MEI")], ids[("MAJU JAYA", "SITI")]
    await page.goto(f"{BASE}/#/payroll/{M}/e/{mei}")
    await page.ev("T.until(() => document.querySelector('#em-tabs [aria-selected=true]'), 'tabs', 6000)")
    expect("tabs", await page.ev("[...document.querySelectorAll('#em-tabs [role=tab]')].map((b) => b.dataset.pane)"), ["fix", "cards", "hours", "pay"])
    expect("opens on To fix", await page.ev("document.querySelector('#em-tabs [aria-selected=true]').dataset.pane"), "fix")
    expect("one pane shown", await page.ev("[...document.querySelectorAll('#em-body > section')].filter((s) => !s.hidden).length"), 1)
    expect("an item to fix", await page.ev("document.querySelectorAll('#em-body .need').length > 0"), True)
    expect("details folded", await page.ev("[...document.querySelectorAll('#em-body .need details')].every((d) => !d.open)"), True)
    await page.ev("document.querySelector('#em-tabs [data-pane=cards]').click()")
    expect("card actions are icons", await page.ev("[...document.querySelectorAll('#em-body .card-row .icon-btn')].slice(0, 3).map((b) => b.title)"),
           ["Check this card", "Move to", "Take off"])
    await page.ev("document.querySelector('#em-body .card-row .icon-btn[title=\"Move to\"]').click()")
    await page.ev("T.until(() => document.getElementById('popup').open, 'move pop-up')")
    expect("move pop-up has the choice", await page.ev("!!document.querySelector('#popup select') && !!T.button('Move', document.getElementById('popup'))"), True)
    await page.ev("closePopup()")
    # an employee with nothing to fix opens on the tab chosen last (Cards)
    await page.ev(f"location.hash = '#/payroll/{M}/e/{siti}'")
    await page.ev("T.until(() => document.getElementById('em-title').textContent.includes('SITI') && document.querySelector('#em-tabs [aria-selected=true]'), 'SITI', 6000)")
    expect("remembered tab", await page.ev("document.querySelector('#em-tabs [aria-selected=true]').dataset.pane"), "cards")
    expect("walk says Next to fix", "Next to fix" in await page.ev("T.text('#em-walk button')"), True)
    await page.ev("T.click('More')")
    expect("Remove employee in the menu", await page.ev("!!T.button('Remove employee', document.getElementById('em-menu'))"), True)
