"""Between the steps: a new employee made in step 2 opens in step 3 (also when step 3 was open before); "files need
you in step 2" finds them even with "All months" chosen, and the company's button opens that company's file."""
from drive import BASE, expect

M = "2026-09"


async def scenario(page, downloads):
    await page.goto(f"{BASE}/#/payroll/{M}")
    await page.ev("T.until(() => location.hash.includes('/e/'), 'step 3 drawn')")       # step 3 has its list now
    # step 2: the August card is taken into September and put on a new employee
    jobs = await page.ev("fetch('/api/jobs').then((r) => r.json())")
    amin = next(j["id"] for j in jobs if "AMIN" in j["name"])
    await page.ev(f"location.hash = '#/check/{amin}'")
    await page.ev("T.until(() => !document.getElementById('ck-needs').hidden, 'needs box')")
    await page.ev("T.click('It is for September 2026', document.getElementById('ck-needs')); T.sleep(1200)")
    if await page.ev("T.text('#ck-needs button').includes('New employee')"):
        await page.ev("T.click('New employee', document.getElementById('ck-needs')); T.sleep(1200)")
    await page.ev("T.until(() => T.text('#ck-foot button').includes('AMIN'), 'See AMIN button')")
    await page.ev("[...document.querySelectorAll('#ck-foot button')].find((b) => b.textContent.includes('AMIN')).click()")
    await page.ev("T.until(() => document.getElementById('em-title').textContent.includes('AMIN'), 'AMIN in step 3', 6000)")
    expect("AMIN opened, not someone else", "AMIN" in await page.ev("document.getElementById('em-title').textContent"), True)
    # a card on nobody: ALI's card taken off; step 2 is left on "All months"
    people = await page.ev(f"fetch('/api/payroll/{M}/people').then((r) => r.json())")
    ali = next(e["id"] for r in people["companies"] if r["company"] == "MAJU JAYA" for e in r["employees"] if e["name"] == "ALI")
    ref = await page.ev(f"fetch('/api/payroll/{M}/employee/{ali}').then((r) => r.json()).then((v) => v.employee.jobs[0])")
    await page.ev(f"fetch('/api/payroll/{M}/take-off', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, "
                  f"body: JSON.stringify({{ ref: {ref!r}, from: {ali!r} }}) }}).then((r) => r.status)")
    await page.ev("location.hash = '#/check'; T.sleep(800)")
    await page.ev("T.set('ck-month', 'all'); T.sleep(800)")
    await page.ev(f"location.hash = '#/payroll/{M}'")
    await page.ev("T.until(() => T.text('#mo-total button').includes('need'), 'files-need-you button', 6000)")
    await page.ev("document.querySelector('#mo-total button').click()")
    await page.ev("T.until(() => !document.getElementById('ck-needs').hidden, 'a file with a problem', 6000)")
    expect("step 2 back on the month", await page.ev("document.getElementById('ck-month').value"), M)
    expect("the problem shown", "whose card is this?" in await page.ev("document.getElementById('ck-needs').textContent"), True)
    # the company's own button: that company's file, with the Company chooser set to it
    await page.ev(f"location.hash = '#/payroll/{M}/c/' + encodeURIComponent('MAJU JAYA')")
    await page.ev("T.until(() => T.text('#co-items button').includes('Go to step 2'), 'company button', 6000)")
    await page.ev("T.click('Go to step 2 →')")
    await page.ev("T.until(() => location.hash.startsWith('#/check/') && document.getElementById('company-filter').value === 'MAJU JAYA', 'chooser set', 6000)")
    await page.ev("T.until(() => !document.getElementById('ck-needs').hidden, 'the company file', 6000)")
    expect("chooser on the company", await page.ev("document.getElementById('company-filter').value"), "MAJU JAYA")
    expect("a MAJU JAYA file with its problem", "whose card is this?" in await page.ev("document.getElementById('ck-needs').textContent"), True)
