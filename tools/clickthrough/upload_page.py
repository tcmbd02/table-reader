"""Step 1 and the step buttons: the page opens on Upload; the steps' buttons are there; old addresses redirect."""
from drive import BASE, expect


async def scenario(page, downloads):
    await page.goto(f"{BASE}/")
    expect("Upload shown", await page.ev("!document.getElementById('upload').hidden"), True)
    expect("step 1 is on", await page.ev("document.getElementById('step-upload').classList.contains('on')"), True)
    expect("just added starts empty", await page.ev("document.getElementById('recent').children.length"), 0)
    await page.goto(f"{BASE}/#/doc/nothing")
    expect("old file address becomes step 2's", await page.ev("location.hash"), "#/check/nothing")
    await page.goto(f"{BASE}/#/payroll/2026-09/look/e1")
    expect("old Look address", await page.ev("location.hash"), "#/payroll/2026-09/e/e1/look")
    await page.goto(f"{BASE}/#/payroll/2026-09/layout/d1/2/h/Total")
    expect("old layout address", await page.ev("location.hash"), "#/check/d1/columns/2/h/Total")
    await page.ev("Storage.prototype.setItem = () => { throw new Error('refused'); }; "
                  "Storage.prototype.getItem = () => { throw new Error('refused'); }; true")
    await page.ev("document.getElementById('step-upload').click(); T.sleep(300)")
    expect("works when storage is refused", await page.ev("!document.getElementById('upload').hidden"), True)
