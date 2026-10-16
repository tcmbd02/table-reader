"""Step 3's company in tabs: To fix · Pay preview (· New in Million when Million lacks some of its employees); a company
with signs in its name (A & B (M)) gets its own Export and settings; the Pay preview's long paragraph is a tooltip."""
from drive import BASE, expect

M = "2026-09"


async def scenario(page, downloads):
    await page.goto(f"{BASE}/#/payroll/{M}/c/" + "A%20%26%20B%20(M)")
    await page.ev("T.until(() => document.querySelector('#co-tabs [role=tab]') && document.getElementById('co-title').textContent.includes('A & B'), 'company tabs', 6000)")
    panes = await page.ev("[...document.querySelectorAll('#co-tabs [role=tab]')].map((b) => b.dataset.pane)")
    expect("tabs", panes[:2], ["fix", "pay"])
    expect("one pane shown", await page.ev("[...document.querySelectorAll('#co-body > section')].filter((s) => !s.hidden).length"), 1)
    expect("head buttons are icons", await page.ev("[...document.querySelectorAll('#company .doc-bar .icon-btn')].map((b) => b.title)"), ["Company settings"])
    await page.ev("document.getElementById('co-export').click()")
    await page.ev("T.until(() => document.getElementById('popup').open, 'export')")
    expect("only A & B ticked", await page.ev("[...document.querySelectorAll('#popup input[data-company]:checked')].map((i) => i.dataset.company)"), ["A & B (M)"])
    await page.ev("closePopup(); document.querySelector('#co-tabs [data-pane=pay]').click()")
    await page.ev("T.until(() => document.querySelector('#co-body table'), 'pay table', 6000)")
    expect("pay pane shown", await page.ev("!document.getElementById('co-pay').hidden && document.getElementById('co-items').hidden"), True)
    expect("legend is a tooltip", await page.ev("!!document.querySelector('#co-pay .icon-btn[title*=\"Million\"]')"), True)
    expect("no long paragraph", await page.ev("document.querySelector('#co-pay p.legend') === null"), True)
    # New in Million: MAJU JAYA's numbers are made by Table Reader and Million's list is not imported
    await page.ev(f"location.hash = '#/payroll/{M}/c/' + encodeURIComponent('MAJU JAYA')")
    await page.ev("T.until(() => document.getElementById('co-title').textContent.includes('MAJU JAYA'), 'MAJU JAYA', 6000)")
    view = await page.ev(f"fetch('/api/payroll/{M}/people').then((r) => r.json())")
    new = next(r for r in view["companies"] if r["company"] == "MAJU JAYA")["million_new"]
    expect("New in Million tab when needed", "new" in await page.ev("[...document.querySelectorAll('#co-tabs [role=tab]')].map((b) => b.dataset.pane)"), bool(new))
    if new:
        await page.ev("document.querySelector('#co-tabs [data-pane=new]').click()")
        expect("its list", await page.ev("document.querySelectorAll('#co-million tr').length"), len(new) + 1)
