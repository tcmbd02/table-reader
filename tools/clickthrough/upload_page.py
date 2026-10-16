"""Step 1 and the step buttons: the page opens on Upload; the steps' buttons are there; old addresses redirect."""
from drive import BASE, expect


async def scenario(page, downloads):
    await page.goto(f"{BASE}/")
    expect("Upload shown", await page.ev("!document.getElementById('upload').hidden"), True)
    expect("step 1 is on", await page.ev("document.getElementById('step-upload').classList.contains('on')"), True)
    expect("just added starts empty", await page.ev("document.getElementById('recent').children.length"), 0)
    jobs = await page.ev("fetch('/api/jobs').then((r) => r.json())")
    zul = next(j["id"] for j in jobs if "ZUL" in j["name"])
    await page.goto(f"{BASE}/#/doc/{zul}")
    expect("old file address becomes step 2's", await page.ev("decodeURIComponent(location.hash)"), f"#/check/{zul}")
    people = await page.ev("fetch('/api/payroll/2026-09/people').then((r) => r.json())")
    someone = people["companies"][0]["employees"][0]["id"]
    await page.goto(f"{BASE}/#/payroll/2026-09/look/{someone}")
    # the Look panel opens and, with nothing to check on the made-up cards, goes back to the employee
    expect("old Look address", (await page.ev("location.hash")).startswith(f"#/payroll/2026-09/e/{someone}"), True)
    await page.goto(f"{BASE}/#/payroll/2026-09/layout/{zul}/1/h/Total")
    expect("old layout address", await page.ev("decodeURIComponent(location.hash)"), f"#/check/{zul}/columns/1/h/Total")
    await page.ev("Storage.prototype.setItem = () => { throw new Error('refused'); }; "
                  "Storage.prototype.getItem = () => { throw new Error('refused'); }; true")
    await page.ev("document.getElementById('step-upload').click(); T.sleep(300)")
    expect("works when storage is refused", await page.ev("!document.getElementById('upload').hidden"), True)
