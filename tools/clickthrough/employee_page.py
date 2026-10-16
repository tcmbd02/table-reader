"""Step 3's employee: Needs you, the window, a card to step 2, Look in place, typing then leaving, Previous / Next,
and a remembered employee removed in another tab."""
from drive import BASE, allow, expect

M = "2026-09"


async def scenario(page, downloads):
    await page.goto(f"{BASE}/")
    people = await page.ev(f"fetch('/api/payroll/{M}/people').then((r) => r.json())")
    ids = {(r["company"], e["name"]): e["id"] for r in people["companies"] for e in r["employees"]}
    print("  employees:", sorted(ids))
    ali, siti, zul = ids[("MAJU JAYA", "ALI")], ids[("MAJU JAYA", "SITI")], ids[("MAJU JAYA", "ZUL")]
    await page.goto(f"{BASE}/#/payroll/{M}/e/{ali}")
    await page.ev("T.until(() => document.querySelector('#em-window .pw-title'), 'window drawn')")
    expect("walk buttons", "Previous" in await page.ev("T.text('#em-walk button')"), True)
    expect("card button", "Check this card" in await page.ev("T.text('#em-cards button')"), True)
    # typing in the name and leaving at once (before the 500 ms wait ends) keeps what was typed (Review Focus 3)
    await page.ev("T.set('ew-name', 'ALI BIN TEST'); document.getElementById('step-check').click(); T.sleep(1500)")
    after = await page.ev(f"fetch('/api/payroll/{M}/employee/{ali}').then((r) => r.json())")
    expect("typed name saved", after["employee"]["name"], "ALI BIN TEST")
    # the card button opens the file in step 2
    await page.goto(f"{BASE}/#/payroll/{M}/e/{ali}")
    await page.ev("T.until(() => document.querySelector('#em-tabs [data-pane=cards]'), 'tabs')")
    await page.ev("document.querySelector('#em-tabs [data-pane=cards]').click(); T.click('Check this card')")
    await page.ev("T.sleep(300)")
    expect("card in step 2", await page.ev("location.hash.startsWith('#/check/')"), True)
    # Previous goes to the employee before in the list
    await page.goto(f"{BASE}/#/payroll/{M}/e/{siti}")
    await page.ev("T.until(() => document.querySelector('#em-window .pw-title'), 'SITI drawn')")
    before = await page.ev("location.hash")
    await page.ev("T.click('‹ Previous'); T.sleep(500)")
    expect("Previous moves", await page.ev("location.hash") != before, True)
    # Look in place and back
    await page.goto(f"{BASE}/#/payroll/{M}/e/{siti}/look")
    await page.ev("T.until(() => location.hash.endsWith('/look') ? !document.getElementById('look').hidden : true, 'look shown'); T.sleep(800)")
    if await page.ev("location.hash.endsWith('/look')"):
        await page.ev("document.getElementById('lk-back').click(); T.sleep(500)")
    expect("back to SITI", await page.ev("location.hash"), f"#/payroll/{M}/e/{siti}")
    # a remembered employee removed in another tab: step 3 starts again from the list (Review Focus 2)
    await page.goto(f"{BASE}/#/payroll/{M}/e/{zul}")
    await page.ev("T.until(() => document.querySelector('#em-window .pw-title'), 'ZUL drawn')")
    allow(f"/employee/{zul}")                          # the page asks for ZUL once more and is told he is gone
    await page.ev(f"fetch('/api/payroll/{M}/employee/{zul}', {{ method: 'DELETE' }}).then((r) => r.status)")
    await page.ev("document.getElementById('step-upload').click(); T.sleep(300); document.getElementById('step-payroll').click()")
    await page.ev(f"T.until(() => location.hash.includes('/e/') && !location.hash.includes({zul!r}), 'another employee', 6000)")
    await page.ev("T.sleep(800)")
    expect("no error left", await page.ev("document.getElementById('em-error').hidden && document.getElementById('mo-error').hidden"), True)
