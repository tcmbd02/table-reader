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
    # Hours: the month as a calendar (1 Sep 2026 is a Tuesday), the day's note on a click, no day-by-day table left
    await page.ev("document.getElementById('em-menu').hidden = true; document.querySelector('#em-tabs [data-pane=hours]').click()")
    expect("30 days in September", await page.ev("document.querySelectorAll('#em-hours .cal .d').length"), 30)
    expect("one blank before Tuesday", await page.ev("document.querySelectorAll('#em-hours .cal .blank').length"), 1)
    expect("Sundays are rest days", await page.ev("[...document.querySelectorAll('#em-hours .cal .d.rest')].map((b) => b.dataset.day)"), ["6", "13", "20", "27"])
    expect("four figures", await page.ev("document.querySelectorAll('#em-hours .fig').length"), 4)
    await page.ev("document.querySelector('#em-hours .cal .d[data-day=\"3\"]').click()")
    expect("day note", await page.ev("document.getElementById('cal-note').textContent.startsWith('3 ')"), True)
    expect("no day-by-day table left", await page.ev("document.getElementById('em-days') === null"), True)
    # MEI's yellow day 9 is marked
    await page.ev(f"location.hash = '#/payroll/{M}/e/{mei}'")
    await page.ev("T.until(() => document.getElementById('em-title').textContent.includes('MEI'), 'MEI again', 6000)")
    await page.ev("T.until(() => document.querySelector('#em-hours .cal .d[data-day=\"9\"]'), 'calendar drawn', 6000)")
    expect("day 9 marked to check", await page.ev("document.querySelector('#em-hours .cal .d[data-day=\"9\"]').classList.contains('bad')"), True)
    # Pay: Million's fields in sub-tabs and groups; typing then another tab at once keeps what was typed (Review Focus 1)
    await page.ev("document.querySelector('#em-tabs [data-pane=pay]').click()")
    expect("sub-tabs", await page.ev("T.text('#em-pay .pw-tabs .tab')"), "Basic Pay & Overtime | Allowance & Deduction | Leave")
    expect("three groups", await page.ev("[...document.querySelectorAll('#em-pay .pw-group h4')].map((h) => h.textContent)"), ["Days", "Overtime", "Time off"])
    expect("no issues list here", await page.ev("document.querySelector('#em-pay .issues') === null"), True)
    await page.ev("T.click('Leave', document.querySelector('#em-pay .pw-tabs'))")
    expect("leave lines", await page.ev("!!document.querySelector('#em-pay table.lines')"), True)
    await page.ev("T.click('Needs checking', document.getElementById('em-pay'))")
    expect("Needs checking opens To fix", await page.ev("document.querySelector('#em-tabs [aria-selected=true]').dataset.pane"), "fix")
    await page.ev("document.querySelector('#em-tabs [data-pane=pay]').click(); T.set('ew-name', 'MEI TABS'); document.querySelector('#em-tabs [data-pane=cards]').click()")
    await page.ev("T.sleep(1200)")
    after = await page.ev(f"fetch('/api/payroll/{M}/employee/{mei}').then((r) => r.json())")
    expect("typed then tab: saved", after["employee"]["name"], "MEI TABS")
    # notes that are not things to fix (leave marked on the card, cards no longer listed) are under To fix too
    await page.ev("emView.result.issues.push({ kind: 'leave', job: null, text: 'The card marks leave on day 4. Type the leave in the Leave table if Million Payroll should count it.' }); emDraw()")
    expect("leave note under To fix", "leave on day 4" in await page.ev("document.getElementById('em-needs').textContent"), True)
