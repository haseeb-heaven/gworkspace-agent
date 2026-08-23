import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1280, "height": 1024})
        await page.goto("http://127.0.0.1:7860")
        await asyncio.sleep(3)
        await page.screenshot(path="screenshot_before_auth.png")

        await page.wait_for_selector('input[type="file"]', state="attached")
        await page.evaluate("document.querySelector('input[type=file]').style.display = 'block'")
        await page.set_input_files('input[type="file"]', 'dummy.json')
        await asyncio.sleep(3)
        await page.screenshot(path="screenshot_after_auth.png")

        await browser.close()

asyncio.run(main())
