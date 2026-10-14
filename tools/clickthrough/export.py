"""Step 3's Export...: the payroll table as CSV for every company, as .xls one file per company (a .zip), the Million
file for one company after its summary, and Export... from a company's panel with only that company ticked."""
import asyncio

from drive import BASE, expect

M = "2026-09"


async def wait_for(folder, name, seconds=8):
    for _ in range(seconds * 10):
        if (folder / name).exists():
            return True
        await asyncio.sleep(0.1)
    return False


async def scenario(page, downloads):
    await page.goto(f"{BASE}/#/payroll/{M}")
    await page.ev("T.until(() => location.hash.includes('/e/'), 'step 3')")
    expect("one Export button", await page.ev("[!!document.getElementById('mo-export-open'), !document.getElementById('mo-run')]"),
           [True, True])
    await page.ev("T.click('Export…'); T.until(() => !document.getElementById('mo-export').hidden, 'panel')")
    picked = await page.ev("[...document.querySelectorAll('#mo-export input:checked')].map((i) => i.dataset.all ? 'all' : i.dataset.company || i.value)")
    print("  ticked at first:", picked)
    expect("defaults", picked, ["table", "csv", "all", "one"])
    await page.ev("T.click('Export', document.getElementById('mo-export'))")
    expect("CSV of every company", await wait_for(downloads, f"Payroll {M}.csv"), True)
    # .xls, two companies, one file per company: one .zip
    await page.ev("document.querySelector('#mo-export input[name=ex-format][value=xls]').click(); "
                  "document.querySelector('#mo-export input[data-company=\"MAJU JAYA\"]').click(); "
                  "document.querySelector('#mo-export input[data-company=\"A & B (M)\"]').click(); "
                  "document.querySelector('#mo-export input[name=ex-split][value=each]').click()")
    expect("All unticked", await page.ev("document.querySelector('#mo-export input[data-all]').checked"), False)
    await page.ev("T.click('Export', document.getElementById('mo-export'))")
    expect("zip of two .xls", await wait_for(downloads, f"Payroll {M} (2 companies).zip"), True)
    # the Million import file of MAJU JAYA: the format choice is off, the summary first, then the file
    await page.ev("document.querySelector('#mo-export input[data-company=\"A & B (M)\"]').click(); "
                  "document.querySelector('#mo-export input[name=ex-what][value=million]').click()")
    expect("format off for Million", await page.ev("document.querySelector('#mo-export input[name=ex-format]').disabled"), True)
    await page.ev("T.click('Export', document.getElementById('mo-export')); T.until(() => !document.getElementById('mo-run-result').hidden, 'summary')")
    await page.ev("T.click('Make the file'); T.until(() => document.getElementById('mo-run-result').textContent.includes('(Million).xls'), 'made', 6000)")
    made = await page.ev("document.getElementById('mo-run-result').textContent")
    print("  made:", made[:160])
    expect("MAJU JAYA's Million file", f"Payroll {M} MAJU JAYA (Million).xls" in made, True)
    # Export... from a company's panel: only that company ticked
    await page.ev(f"location.hash = '#/payroll/{M}/c/' + encodeURIComponent('A & B (M)')")
    await page.ev("T.until(() => !document.getElementById('company').hidden, 'company'); document.getElementById('co-export').click(); "
                  "T.until(() => !document.getElementById('mo-export').hidden, 'panel again')")
    ticked = await page.ev("[...document.querySelectorAll('#mo-export input[data-company]:checked')].map((i) => i.dataset.company)")
    expect("only A & B ticked", ticked, ["A & B (M)"])
