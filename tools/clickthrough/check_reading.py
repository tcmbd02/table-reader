"""Step 2 while a file is being read: progress in the list and on the file, the Month list stays put, then the file
updates by itself, also after leaving step 2 and coming back; step 3 then says what joined by itself."""
from drive import BASE, expect


async def scenario(page, downloads):
    await page.goto(f"{BASE}/#/check")
    await page.ev("T.until(() => document.getElementById('ck-month').options.length > 1, 'months'); T.set('ck-month', 'all'); "
                  "T.until(() => T.text('#ck-files').includes('SLOW'), 'slow file listed', 8000)")
    jobs = await page.ev("fetch('/api/jobs').then((r) => r.json())")
    slow = next(j["id"] for j in jobs if "SLOW" in j["name"])
    await page.ev("T.set('ck-month', '2026-09'); T.sleep(800)")
    await page.goto(f"{BASE}/#/check/{slow}")
    await page.ev("T.until(() => document.getElementById('doc-name').textContent.includes('SLOW'), 'open')")
    expect("Download off while reading", await page.ev("document.getElementById('download').disabled"), True)
    expect("no needs box while reading", await page.ev("document.getElementById('ck-needs').hidden"), True)
    # the Month list is not rebuilt under the user while the list follows the reading (it would close if open)
    await page.ev("window.firstMonth = document.getElementById('ck-month').options[0]; T.sleep(4500)")
    expect("Month list kept", await page.ev("document.getElementById('ck-month').options[0] === window.firstMonth"), True)
    # leave step 2 while it is being read, come back after it finished: the file shows its table
    await page.ev("document.getElementById('step-payroll').click(); T.sleep(300)")
    for _ in range(40):
        status = await page.ev(f"fetch('/api/jobs/{slow}').then((r) => r.json()).then((j) => j.status)")
        if status == "done":
            break
        await page.ev("T.sleep(500)")
    await page.ev("document.getElementById('step-check').click()")
    await page.ev("T.until(() => document.getElementById('download').disabled === false, 'finished on coming back', 8000)")
    expect("table shown", await page.ev("document.querySelectorAll('#pages table').length > 0"), True)
    expect("list shows it finished", "Reading" in await page.ev("T.text('#ck-files .side-item.on')"), False)
    # step 2 opened the month when the file finished: step 3 says what joined by itself
    await page.ev("document.getElementById('step-payroll').click()")
    await page.ev("T.until(() => !document.getElementById('bell-count').hidden, 'a message in the bell', 6000)")
    await page.ev("T.click('Messages')")
    print("  note:", await page.ev("T.text('#bell-list .msg-line')"))
    expect("note names the new worker", "SLOW" in await page.ev("T.text('#bell-list .msg-line')"), True)
