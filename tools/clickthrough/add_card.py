"""Step 3's employee: "Add a time card" offers the company's other cards (on nobody / on another employee), adds a
card of another month, and moves one from another employee after a confirm."""
from drive import BASE, expect

M = "2026-09"


async def scenario(page, downloads):
    await page.goto(f"{BASE}/")
    people = await page.ev(f"fetch('/api/payroll/{M}/people').then((r) => r.json())")
    ids = {(r["company"], e["name"]): e["id"] for r in people["companies"] for e in r["employees"]}
    ali, siti = ids[("MAJU JAYA", "ALI")], ids[("MAJU JAYA", "SITI")]
    await page.goto(f"{BASE}/#/payroll/{M}/e/{ali}")
    await page.ev("T.until(() => document.getElementById('em-add'), 'add a time card', 6000)")
    offered = await page.ev("[...document.querySelectorAll('#em-add option')].map((o) => o.textContent)")
    groups = await page.ev("[...document.querySelectorAll('#em-add optgroup')].map((g) => g.label)")
    print("  offered:", offered, "groups:", groups)
    expect("only MAJU JAYA cards", all("A & B" not in o for o in offered), True)
    expect("not ALI's own card", any("ALI" in o for o in offered), False)
    expect("August card on nobody", any("AMIN" in o and "August 2026" in o for o in offered), True)
    expect("SITI's card marked", any("SITI" in o and "now on SITI" in o for o in offered), True)
    # a card of another month, on nobody: added to ALI
    await page.ev("{ const s = document.getElementById('em-add'); s.value = [...s.options].find((o) => o.textContent.includes('AMIN')).value; }"
                  "T.click('Add', document.getElementById('em-cards'))")
    await page.ev("T.until(() => T.text('#em-cards li strong').includes('AMIN'), 'AMIN card on ALI', 6000)")
    expect("ALI has 2 cards", await page.ev("document.querySelectorAll('#em-cards li').length"), 2)
    # a card on another employee: moved here after the confirm
    await page.ev("window.asked = ''; window.confirm = (q) => { window.asked = q; return true; }; "
                  "{ const s = document.getElementById('em-add'); s.value = [...s.options].find((o) => o.textContent.includes('SITI')).value; }"
                  "T.click('Add', document.getElementById('em-cards'))")
    await page.ev("T.until(() => T.text('#em-cards li strong').includes('SITI'), 'SITI card on ALI', 6000)")
    expect("asked first", await page.ev("window.asked"), "Move this card from SITI to ALI?")
    siti_view = await page.ev(f"fetch('/api/payroll/{M}/employee/{siti}').then((r) => r.json())")
    expect("SITI has no card now", siti_view["employee"]["jobs"], [])
    expect("figures redrawn", await page.ev("document.getElementById('em-error').hidden"), True)
