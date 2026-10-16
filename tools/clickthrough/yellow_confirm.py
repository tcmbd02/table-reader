"""Step 2 to payroll while yellow cells are left: every way there asks "There are still yellow cells…" (No stays,
Yes goes); also from a file without yellow cells while another file in the list has some; after the last yellow cell
is accepted nothing asks. Run with YELLOW_FILE=1 (MEI's card has one yellow cell)."""
from drive import BASE, expect

M = "2026-09"
Q = "There are still yellow cells. Are you sure you want to go to payroll?"
ANSWER = "window.asked = ''; window.confirm = (q) => { window.asked = q; return {yes}; };"


async def go(page, how, yes):
    """Press one of the three ways to payroll, answering the question with yes / no; what was asked, where it is now."""
    await page.ev(ANSWER.replace("{yes}", "true" if yes else "false"))
    if how == "step":
        await page.ev("document.getElementById('step-payroll').click()")
    else:
        await page.ev(f"[...document.querySelectorAll('#ck-foot button')].find((b) => b.textContent.includes({how!r})).click()")
    await page.ev("T.sleep(400)")
    return await page.ev("window.asked"), await page.ev("location.hash")


async def scenario(page, downloads):
    await page.goto(f"{BASE}/#/payroll/{M}")                              # the working month: September
    await page.ev("T.until(() => document.getElementById('people') && !document.getElementById('people').hidden, 'step 3')")
    jobs = await page.ev("fetch('/api/jobs').then((r) => r.json())")
    mei = next(j["id"] for j in jobs if "MEI" in j["name"])
    ali = next(j["id"] for j in jobs if "ALI" in j["name"])
    await page.ev(f"location.hash = '#/check/{mei}'")
    await page.ev("T.until(() => T.text('#ck-foot button').includes('in payroll →'), 'foot with See … in payroll', 6000)")
    expect("step 2 badge counts the yellow cell", await page.ev("document.getElementById('step-check-n').textContent"), "1")
    for how in ("Go to payroll for", "in payroll →", "step"):
        asked, where = await go(page, how, yes=False)
        expect(f"{how}: asked", asked, Q)
        expect(f"{how}: No stays in step 2", where.startswith("#/check/"), True)
    asked, where = await go(page, "in payroll →", yes=True)
    expect("See … in payroll: Yes goes to the employee", (asked, where.startswith(f"#/payroll/{M}/e/")), (Q, True))
    # back in step 2 (a new visit): asked again; the step button with Yes opens step 3
    await page.ev("document.getElementById('step-check').click()")
    await page.ev("T.until(() => location.hash.startsWith('#/check/') && T.text('#ck-foot button').includes('Go to payroll'), 'step 2 again', 6000)")
    asked, where = await go(page, "step", yes=True)
    expect("step button: Yes opens step 3", (asked, where.startswith(f"#/payroll/{M}")), (Q, True))
    # ALI's file has no yellow cell, but MEI's in the list has: still asked
    await page.ev(f"location.hash = '#/check/{ali}'")
    await page.ev("T.until(() => document.getElementById('doc-name').textContent.includes('ALI') && T.text('#ck-foot button').includes('Go to payroll'), 'ALI open', 6000)")
    asked, where = await go(page, "Go to payroll for", yes=True)
    expect("a file without yellow cells: still asked", (asked, where.startswith(f"#/payroll/{M}")), (Q, True))
    # MEI's yellow cell accepted (Enter): nothing asks any more
    await page.ev(f"location.hash = '#/check/{mei}'")
    await page.ev("T.until(() => document.querySelector('#doc .cell.flag input'), 'the yellow cell', 6000)")
    await page.ev("{ const i = document.querySelector('#doc .cell.flag input'); i.focus(); "
                  "i.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })); }")
    await page.ev("T.until(() => !document.querySelector('#doc .cell.flag'), 'accepted', 6000)")
    await page.ev("T.until(() => document.getElementById('step-check-n').hidden, 'badge gone', 6000)")
    asked, where = await go(page, "Go to payroll for", yes=False)
    expect("no yellow cells: not asked, goes on", (asked, where.startswith(f"#/payroll/{M}")), ("", True))
    await page.ev("document.getElementById('step-check').click(); T.sleep(800)")
    asked, where = await go(page, "step", yes=False)
    expect("no yellow cells: step button goes on", (asked, where.startswith(f"#/payroll/{M}")), ("", True))
