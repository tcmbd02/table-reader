"""Step 3's Export (a pop-up): the payroll table as CSV for every company, as .xls one file per company (a .zip), the
Million file for one company with its summary inside the pop-up and its result in the bell (Open folder), the pop-up
staying inside the window, and Export from a company's panel with only that company ticked."""
import asyncio

from drive import BASE, expect

M = "2026-09"


async def wait_for(folder, name, seconds=8):
    for _ in range(seconds * 10):
        if (folder / name).exists():
            return True
        await asyncio.sleep(0.1)
    return False


async def open_export(page):
    await page.ev("T.click('Export')")
    await page.ev("T.until(() => document.getElementById('popup').open && document.querySelector('#popup input[name=ex-what]'), 'export pop-up')")


async def scenario(page, downloads):
    await page.goto(f"{BASE}/#/payroll/{M}")
    await page.ev("T.until(() => location.hash.includes('/e/'), 'step 3')")
    expect("old panel and banner gone", await page.ev("[document.getElementById('mo-export'), document.getElementById('mo-run-result')]"), [None, None])
    await open_export(page)
    picked = await page.ev("[...document.querySelectorAll('#popup input:checked')].map((i) => i.dataset.all ? 'all' : i.dataset.company || i.value)")
    print("  ticked at first:", picked)
    expect("defaults", picked, ["table", "all", "csv", "one"])
    await page.ev("T.click('Export', document.getElementById('popup-foot'))")
    expect("CSV of every company", await wait_for(downloads, f"Payroll {M}.csv"), True)
    await page.ev("T.until(() => !document.getElementById('popup').open, 'closed after the download', 6000)")
    # .xls, two companies, one file per company: one .zip
    await open_export(page)
    await page.ev("document.querySelector('#popup input[name=ex-format][value=xls]').click(); "
                  "document.querySelector('#popup input[data-company=\"MAJU JAYA\"]').click(); "
                  "document.querySelector('#popup input[data-company=\"A & B (M)\"]').click(); "
                  "document.querySelector('#popup input[name=ex-split][value=each]').click()")
    expect("All unticked", await page.ev("document.querySelector('#popup input[data-all]').checked"), False)
    await page.ev("T.click('Export', document.getElementById('popup-foot'))")
    expect("zip of two .xls", await wait_for(downloads, f"Payroll {M} (2 companies).zip"), True)
    # the Million import file of MAJU JAYA: the format choice is off, the summary in the pop-up, then the file
    await open_export(page)
    await page.ev("document.querySelector('#popup input[data-company=\"MAJU JAYA\"]').click(); "
                  "document.querySelector('#popup input[name=ex-what][value=million]').click()")
    expect("format off for Million", await page.ev("document.querySelector('#popup input[name=ex-format]').disabled"), True)
    await page.ev("T.click('Export', document.getElementById('popup-foot'))")
    await page.ev("T.until(() => document.querySelector('#popup .summary'), 'summary in the pop-up', 6000)")
    expect("summary says who goes in", "Going in" in await page.ev("document.querySelector('#popup .summary').textContent"), True)
    await page.ev("T.click('Make the file', document.getElementById('popup-foot'))")
    await page.ev("T.until(() => !document.getElementById('popup').open, 'made and closed', 6000)")
    await page.ev("T.click('Messages')")
    await page.ev("T.until(() => !document.getElementById('bell-list').hidden, 'bell open')")
    made = await page.ev("T.text('#bell-list .msg')")
    print("  made:", made[:160])
    expect("made, in the bell", "MAJU JAYA" in made and "Million file" in made, True)
    expect("its name in the detail", f"Payroll {M} MAJU JAYA (Million).xls" in await page.ev("document.querySelector('#bell-list .msg details').textContent"), True)
    expect("Open folder", await page.ev("!!T.button('Open folder', document.getElementById('bell-list'))"), True)
    await page.ev("document.body.click()")
    # the pop-up stays inside the window and scrolls inside itself (Review Focus 5)
    await open_export(page)
    # as many companies as the real month (about 30; the made-up month has 3): 40 more chips in the list
    await page.ev("const chips = document.querySelector('#popup .chips'); for (let i = 1; i <= 40; i++) "
                  "chips.append(el('label', { class: 'chip' }, el('input', { type: 'checkbox' }), el('span', { text: `COMPANY ${i} SDN BHD` }))); 'ok'")
    expect("never taller than the window", await page.ev("document.getElementById('popup').getBoundingClientRect().bottom <= innerHeight"), True)
    expect("its buttons on the screen", await page.ev("document.getElementById('popup-foot').getBoundingClientRect().bottom <= innerHeight"), True)
    expect("its body scrolls", await page.ev("(() => { const b = document.getElementById('popup-body'); return b.scrollHeight > b.clientHeight; })()"), True)
    await page.ev("closePopup()")
    # Export from a company's panel: only that company ticked
    await page.ev(f"location.hash = '#/payroll/{M}/c/' + encodeURIComponent('A & B (M)')")
    await page.ev("T.until(() => !document.getElementById('company').hidden && document.getElementById('co-title').textContent.includes('A & B'), 'company', 6000)")
    await page.ev("document.getElementById('co-export').click()")
    await page.ev("T.until(() => document.getElementById('popup').open, 'pop-up again')")
    ticked = await page.ev("[...document.querySelectorAll('#popup input[data-company]:checked')].map((i) => i.dataset.company)")
    expect("only A & B ticked", ticked, ["A & B (M)"])
