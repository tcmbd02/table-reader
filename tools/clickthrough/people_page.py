"""Step 3: the list, an employee chosen by itself, a company with signs in its name, search, an empty month."""
from drive import BASE, expect


async def scenario(page, downloads):
    await page.goto(f"{BASE}/#/payroll/2026-09")
    await page.ev("T.until(() => location.hash.includes('/e/'), 'an employee is chosen')")
    expect("step 3 on", await page.ev("document.getElementById('step-payroll').classList.contains('on')"), True)
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
    await page.ev("document.getElementById('mo-run').click(); T.until(() => !document.getElementById('mo-run-result').hidden, 'summary')")
    expect("summary shown", "Million file" in await page.ev("document.getElementById('mo-run-result').textContent"), True)
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
