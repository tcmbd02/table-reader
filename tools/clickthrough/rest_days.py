"""Month settings: "Rest days every week" - Sunday ticked in a new month; ticking Saturday makes every Saturday a rest
day but leaves a public holiday alone; one Sunday made a working day by hand half-ticks Sunday; Save sends it all."""
from drive import BASE, expect

M = "2026-09"          # 1 September 2026 is a Tuesday: Saturdays 5, 12, 19, 26; Sundays 6, 13, 20, 27


async def scenario(page, downloads):
    await page.goto(f"{BASE}/#/payroll/{M}")
    await page.ev("T.until(() => location.hash.includes('/e/'), 'step 3'); T.click('Month settings')")
    await page.ev("T.until(() => document.querySelector('#popup input[data-weekday]'), 'weekly ticks')")
    box = "document.querySelector('#popup input[data-weekday=\"{}\"]')"
    day = "[...document.querySelectorAll('#popup .days button')][{}]"
    expect("Sunday ticked", await page.ev(box.format(0) + ".checked"), True)
    expect("Saturday not ticked", await page.ev(box.format(6) + ".checked"), False)
    # day 5 (a Saturday) made a public holiday: working -> rest -> public holiday
    await page.ev(day.format(4) + ".click(); " + day.format(4) + ".click()")
    await page.ev(box.format(6) + ".click()")
    classes = await page.ev(f"[4, 11, 18, 25].map((i) => {day.format('i')}.className)")
    expect("Saturdays rest, the holiday kept", classes, ["day holiday", "day rest", "day rest", "day rest"])
    expect("Saturday now ticked", await page.ev(box.format(6) + ".checked"), True)
    # one Sunday (13) made a working day by hand: rest -> public holiday -> working
    await page.ev(day.format(12) + ".click(); " + day.format(12) + ".click()")
    expect("Sunday half-ticked", await page.ev(f"[{box.format(0)}.checked, {box.format(0)}.indeterminate]"), [False, True])
    await page.ev("T.click('Save', document.getElementById('popup')); T.until(() => !document.getElementById('popup').open, 'saved')")
    saved = await page.ev(f"fetch('/api/payroll/{M}/people').then((r) => r.json()).then((v) => v.settings.day_types)")
    expect("saved calendar", [saved[d] for d in ("5", "12", "19", "26", "6", "13", "20")],
           ["holiday", "rest", "rest", "rest", "rest", "work", "rest"])
    # unticking Saturday makes them working days again (the holiday stays)
    await page.ev("T.click('Month settings'); T.until(() => document.querySelector('#popup input[data-weekday]'), 'again')")
    await page.ev(box.format(6) + ".click()")
    classes = await page.ev(f"[4, 11].map((i) => {day.format('i')}.className)")
    expect("unticked: working again, holiday kept", classes, ["day holiday", "day work"])
