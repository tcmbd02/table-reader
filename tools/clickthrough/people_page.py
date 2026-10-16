"""Step 3: the list, an employee chosen by itself, a company with signs in its name, search, an empty month."""
from drive import BASE, expect


async def scenario(page, downloads):
    await page.goto(f"{BASE}/#/payroll/2026-09")
    await page.ev("T.until(() => location.hash.includes('/e/'), 'an employee is chosen')")
    expect("step 3 on", await page.ev("document.getElementById('step-payroll').classList.contains('on')"), True)
    # the month bar is icons with their words as tooltips; one short status line; the list's marks are icons
    expect("month bar is icons", await page.ev("[...document.querySelectorAll('#people > .doc-bar .icon-btn')].map((b) => b.title)"),
           ["Month before", "Month after", "Messages", "Month settings", "Import employee list from Million"])
    view = await page.ev("fetch('/api/payroll/2026-09/people').then((r) => r.json())")
    fix = sum(1 for r in view["companies"] for e in r["employees"] if e["status"] == "needs")
    expect("status line", await page.ev("T.text('#mo-total .stat')"), f"{view['ready_employees']} ready | {fix} to fix")
    expect("ready shown as a tick", await page.ev("!!document.querySelector('#pp-list .side-item use[href$=\"circle-check\"]')"), True)
    expect("word kept as tooltip", await page.ev("[...document.querySelectorAll('#pp-list .side-item .pill')].find((p) => p.querySelector('use[href$=\"circle-check\"]')).title"), "Ready")
    expect("not checked with Million: a dot on the list button", await page.ev("!!document.querySelector('#people > .doc-bar .warn-dot')"), True)
    heads = await page.ev("T.text('#pp-list .side-head strong')")
    print("  companies:", heads)
    expect("A & B (M) listed", "A & B (M)" in heads, True)
    await page.ev("[...document.querySelectorAll('#pp-list .side-head')].find((b) => b.textContent.includes('A & B (M)')).click(); T.sleep(800)")
    expect("company address", await page.ev("decodeURIComponent(location.hash)"), "#/payroll/2026-09/c/A & B (M)")
    expect("company panel shows it", await page.ev("document.getElementById('co-title').textContent"), "A & B (M) - September 2026")
    expect("pay table drawn", await page.ev("T.until(() => document.querySelector('#co-pay-table table'), 'pay table')"), True)
    # search filters the list
    await page.ev("T.set('pp-search', 'siti'); T.sleep(200)")
    found = await page.ev("T.text('#pp-list .side-item')")
    expect("search keeps SITI only", "SITI" in found and "ALI" not in found, True)
    await page.ev("T.set('pp-search', ''); T.sleep(200)")
    # the month bar's Million file summary opens
    await page.ev("T.click('Export')")
    await page.ev("T.until(() => document.getElementById('popup').open, 'export'); "
                  "document.querySelector('#popup input[name=ex-what][value=million]').click(); "
                  "T.click('Export', document.getElementById('popup-foot'))")
    await page.ev("T.until(() => document.querySelector('#popup .summary'), 'summary', 6000)")
    expect("summary shown", "Going in" in await page.ev("document.querySelector('#popup .summary').textContent"), True)
    await page.ev("closePopup()")
    # step 2's Company chooser also filters step 3: step 3 says so and can show everyone again
    await page.goto(f"{BASE}/#/check")
    await page.ev("T.until(() => document.getElementById('company-filter'), 'chooser'); T.set('company-filter', 'A & B (M)'); T.sleep(300)")
    await page.ev("document.getElementById('step-payroll').click()")
    await page.ev("T.until(() => !document.getElementById('pp-filter').hidden, 'filter line', 6000)")
    expect("only A & B listed", await page.ev("T.text('#pp-list .side-head strong')"), "A & B (M)")
    await page.ev("T.click('Show all companies'); T.sleep(300)")
    expect("everyone again", "MAJU JAYA" in await page.ev("T.text('#pp-list .side-head strong')"), True)
    expect("line gone", await page.ev("document.getElementById('pp-filter').hidden"), True)
    # an empty month
    await page.goto(f"{BASE}/#/payroll/2026-03")
    await page.ev("T.until(() => !document.getElementById('pp-empty').hidden, 'empty month')")
    expect("empty month stays put", await page.ev("location.hash"), "#/payroll/2026-03")
    await page.ev("T.click('Go to step 1')")
    await page.ev("T.sleep(300)")
    expect("to step 1", await page.ev("!document.getElementById('upload').hidden"), True)
