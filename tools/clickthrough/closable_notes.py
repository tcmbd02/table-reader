"""Step 3's messages at the top ("Added by themselves…", "Million file made…") are said once: each has a × that closes
it, and both close when another employee or company is opened; going to step 3 from step 2 still shows the note."""
from drive import BASE, expect

M = "2026-09"
NOTE = ('[{"added": {"added": [{"name": "AMIN", "cards": 1}], "joined": [], "skipped": [], "unnamed": [], "no_month": [], '
        '"from_million": 0, "new_numbers": 1}, "numbered": 0}]')


async def make_million_file(page):
    await page.ev("if (document.getElementById('mo-export').hidden) T.click('Export…'); T.until(() => !document.getElementById('mo-export').hidden, 'panel')")
    await page.ev("document.querySelector('#mo-export input[name=ex-what][value=million]').click(); "
                  "T.click('Export', document.getElementById('mo-export')); T.until(() => !document.getElementById('mo-run-result').hidden, 'summary')")
    await page.ev("T.click('Make the file'); T.until(() => document.getElementById('mo-run-result').textContent.includes('(Million).xls'), 'made', 6000)")


def hidden(id_):
    return f"document.getElementById('{id_}').hidden"


async def scenario(page, downloads):
    await page.goto(f"{BASE}/#/check")
    await page.ev("T.until(() => location.hash.startsWith('#/check/'), 'step 2')")
    people = await page.ev(f"fetch('/api/payroll/{M}/people').then((r) => r.json())")
    ids = {(r["company"], e["name"]): e["id"] for r in people["companies"] for e in r["employees"]}
    ali, siti = ids[("MAJU JAYA", "ALI")], ids[("MAJU JAYA", "SITI")]
    # step 2 → step 3 with a note kept for it: shown, and it stays while the first employee opens by itself
    await page.ev(f"sessionStorage.setItem('notes.{M}', {NOTE!r}); location.hash = '#/payroll/{M}'")
    await page.ev("T.until(() => location.hash.includes('/e/') && !document.getElementById('employee').hidden, 'step 3', 6000)")
    await page.ev("T.sleep(500)")
    expect("note shown", await page.ev(f"!{hidden('mo-info')} && document.getElementById('mo-info').textContent.includes('AMIN')"), True)
    # another employee opened: the note is gone, and stays gone
    await page.ev(f"location.hash = '#/payroll/{M}/e/{siti}'")
    await page.ev("T.until(() => document.getElementById('em-title').textContent.includes('SITI'), 'SITI', 6000); T.sleep(1200)")
    expect("note closed on another employee", await page.ev(hidden("mo-info")), True)
    # the note's ×
    await page.ev(f"document.getElementById('step-check').click(); T.until(() => location.hash.startsWith('#/check/'), 'step 2 again', 6000)")
    await page.ev(f"sessionStorage.setItem('notes.{M}', {NOTE!r}); document.getElementById('step-payroll').click()")
    await page.ev("T.until(() => !document.getElementById('mo-info').hidden, 'note again', 6000)")
    await page.ev("document.querySelector('#mo-info .banner-close').click(); T.sleep(1200)")
    expect("× closes the note", await page.ev(hidden("mo-info")), True)
    # the Million file message: × closes it
    await make_million_file(page)
    await page.ev("document.querySelector('#mo-run-result .banner-close').click()")
    expect("× closes the Million message", await page.ev(hidden("mo-run-result")), True)
    # ... and opening another employee or a company closes it
    await make_million_file(page)
    await page.ev(f"location.hash = '#/payroll/{M}/e/{ali}'")
    await page.ev("T.until(() => document.getElementById('em-title').textContent.includes('ALI'), 'ALI', 6000)")
    expect("Million message closed on another employee", await page.ev(hidden("mo-run-result")), True)
    await make_million_file(page)
    await page.ev(f"location.hash = '#/payroll/{M}/c/' + encodeURIComponent('A & B (M)')")
    await page.ev("T.until(() => !document.getElementById('company').hidden, 'company', 6000)")
    expect("Million message closed on a company", await page.ev(hidden("mo-run-result")), True)
