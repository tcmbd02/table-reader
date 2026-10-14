"""Step 2: the file list, a file with a problem, the column choice in place, the buttons on, empty and stale cases."""
from drive import BASE, expect


async def scenario(page, downloads):
    await page.goto(f"{BASE}/#/check")
    await page.ev("T.until(() => location.hash.length > '#/check/'.length && location.hash.startsWith('#/check/'), 'a file is chosen')")
    expect("step 2 on", await page.ev("document.getElementById('step-check').classList.contains('on')"), True)
    print("  files:", await page.ev("T.text('#ck-files .side-item strong')"))
    # the August card is on nobody in August: listed so a wrong month can be put right, marked as not in this month
    amin = await page.ev("[...document.querySelectorAll('#ck-files .side-item')].find((b) => b.textContent.includes('AMIN')).textContent")
    expect("August card marked", "Not in this month" in amin, True)
    jobs = await page.ev("fetch('/api/jobs').then((r) => r.json())")
    ids = {j["name"]: j["id"] for j in jobs}
    zul = next(v for k, v in ids.items() if "ZUL" in k)
    await page.goto(f"{BASE}/#/check/{zul}")
    await page.ev("T.until(() => document.getElementById('doc-name').textContent.includes('ZUL'), 'ZUL open')")
    expect("Download enabled", await page.ev("document.getElementById('download').disabled"), False)
    await page.ev("T.until(() => document.getElementById('ck-foot').children.length > 1, 'foot')")
    foot = await page.ev("T.text('#ck-foot button')")
    print("  foot:", foot)
    expect("foot buttons", "Go to payroll for September 2026 →" in foot and "in payroll →" in foot, True)
    await page.ev("[...document.querySelectorAll('#ck-foot button')].find((b) => b.textContent.endsWith('in payroll →')).click(); T.sleep(300)")
    expect("goes to step 3's employee", await page.ev("location.hash.startsWith('#/payroll/2026-09/e/')"), True)
    # All months shows every file; its problems are not asked about there
    await page.goto(f"{BASE}/#/check")
    await page.ev("T.until(() => document.getElementById('ck-month').options.length > 1, 'months'); "
                  "T.set('ck-month', 'all'); T.sleep(800)")
    expect("All months lists the August card", "AMIN AUG" in await page.ev("T.text('#ck-files .side-item strong')"), True)
    expect("no problem marks with All months", "Not in this month" in await page.ev("T.text('#ck-files')"), False)
    await page.ev("T.set('ck-month', '2026-09'); T.sleep(800)")
    # a month with no files for the chosen company (MAJU JAYA's August card is listed in every month, on purpose)
    await page.ev("T.set('company-filter', 'A & B (M)'); T.sleep(300); T.set('ck-month', '2026-03'); T.sleep(1500)")
    expect("empty month", await page.ev("document.getElementById('ck-empty-text').textContent"),
           "No files for March 2026. Choose “All months” to see every file.")
    expect("the list is empty", await page.ev("document.getElementById('ck-files').children.length"), 0)
    await page.ev("T.set('company-filter', ''); T.sleep(300)")
    # a remembered file that is gone
    await page.ev("T.set('ck-month', '2026-09'); T.sleep(800); sessionStorage.setItem('place.check', '#/check/gone-file')")
    await page.goto(f"{BASE}/#/check/gone-file")
    await page.ev("T.until(() => location.hash !== '#/check/gone-file', 'redirect')")
    expect("a gone file opens step 2's first file", await page.ev("location.hash.length > '#/check/'.length && location.hash.startsWith('#/check/')"), True)
    # the column choice opens under the file and closes again
    await page.goto(f"{BASE}/#/check/{zul}/columns/1")
    await page.ev("T.until(() => !document.getElementById('ly-body').hidden, 'columns open')")
    expect("the file stays under it", await page.ev("document.getElementById('doc-name').textContent.includes('ZUL')"), True)
    await page.ev("document.getElementById('ly-back').click(); T.sleep(500)")
    expect("closed", await page.ev("document.getElementById('layout').hidden"), True)
    expect("back on the file", await page.ev("decodeURIComponent(location.hash)"), f"#/check/{zul}")
