"""Step 2 while a file is being read: progress in the list and on the file, then it updates by itself."""
from drive import BASE, expect


async def scenario(page, downloads):
    await page.goto(f"{BASE}/#/check")
    await page.ev("T.until(() => document.getElementById('ck-month').options.length > 1, 'months'); T.set('ck-month', 'all'); "
                  "T.until(() => T.text('#ck-files').includes('SLOW'), 'slow file listed', 8000)")
    jobs = await page.ev("fetch('/api/jobs').then((r) => r.json())")
    slow = next(j["id"] for j in jobs if j["name"].startswith("SLOW"))
    await page.goto(f"{BASE}/#/check/{slow}")
    await page.ev("T.until(() => document.getElementById('doc-name').textContent.startsWith('SLOW'), 'open')")
    expect("Download off while reading", await page.ev("document.getElementById('download').disabled"), True)
    expect("no needs box while reading", await page.ev("document.getElementById('ck-needs').hidden"), True)
    await page.ev("T.until(() => document.getElementById('download').disabled === false, 'finished', 15000)")
    await page.ev("T.sleep(4500)")
    expect("list shows it finished", "Reading" in await page.ev("T.text('#ck-files .side-item.on')"), False)
