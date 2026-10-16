"""Step 3's pop-up: Month settings open over the page (Esc and × close it, Save saves and closes), an open pop-up closes
when the address changes, and Company settings use the same pop-up."""
from drive import BASE, expect

M = "2026-09"


async def scenario(page, downloads):
    await page.goto(f"{BASE}/#/payroll/{M}")
    await page.ev("T.until(() => location.hash.includes('/e/'), 'step 3')")
    await page.ev("T.click('Month settings'); T.until(() => document.getElementById('popup').open, 'open')")
    expect("settings in the pop-up", await page.ev("!!document.querySelector('#popup input[data-weekday]')"), True)
    expect("its icon is drawn", await page.ev("document.querySelector('#popup-title .ico').getBoundingClientRect().width > 0"), True)
    await page.ev("document.getElementById('popup').dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true})); T.sleep(200)")
    expect("Esc closes", await page.ev("document.getElementById('popup').open"), False)
    await page.ev("T.click('Month settings'); T.until(() => document.getElementById('popup').open, 'open again')")
    await page.ev("T.click('Close', document.getElementById('popup')); T.sleep(200)")
    expect("× closes", await page.ev("document.getElementById('popup').open"), False)
    # Save: Saturday as a weekly rest day is saved, and the pop-up closes
    await page.ev("T.click('Month settings'); T.until(() => document.getElementById('popup').open, 'open for save')")
    await page.ev("document.querySelector('#popup input[data-weekday=\"6\"]').click(); T.click('Save', document.getElementById('popup'))")
    await page.ev("T.until(() => !document.getElementById('popup').open, 'saved and closed', 6000)")
    s = await page.ev(f"fetch('/api/payroll/{M}/people').then((r) => r.json()).then((v) => v.settings.day_types['5'])")
    expect("5 Sep (Sat) is a rest day", s, "rest")
    # an open pop-up closes when the address changes (Review Focus 2)
    await page.ev("T.click('Month settings'); T.until(() => document.getElementById('popup').open, 'open before leaving')")
    await page.ev("document.getElementById('step-check').click(); T.until(() => /^#\/check\/./.test(location.hash) && !document.getElementById('doc').hidden, 'step 2 settled', 6000)")
    expect("closed on leaving step 3", await page.ev("document.getElementById('popup').open"), False)
    # company settings: the same pop-up, over the company
    await page.ev(f"location.hash = '#/payroll/{M}/c/' + encodeURIComponent('MAJU JAYA')")
    await page.ev("T.until(() => !document.getElementById('company').hidden && document.getElementById('co-title').textContent.includes('MAJU JAYA'), 'company drawn', 6000)")
    await page.ev("T.click('Company settings')")
    await page.ev("T.until(() => document.getElementById('popup').open, 'company settings open')")
    expect("company settings title", "MAJU JAYA" in await page.ev("document.getElementById('popup-title').textContent"), True)
    expect("one pop-up only", await page.ev("document.querySelectorAll('dialog[open]').length"), 1)
