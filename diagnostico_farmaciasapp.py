"""
Diagnóstico: inspeciona seletores de imagem na farmaciasapp.
Conecta ao Chrome já aberto (porta 9222).
"""
import asyncio
from playwright.async_api import async_playwright

URL = "https://www.farmaciasapp.com.br/creme-para-m-os-mandarina-e-jasmim-panvel-instantes-30g"
CDP_URL = "http://localhost:9222"


async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp(CDP_URL)
        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = await context.new_page()

        print(f"Abrindo: {URL}\n")
        await page.goto(URL, wait_until="domcontentloaded", timeout=30000)

        # Aguarda mais tempo para JS carregar
        for segundos in [1, 2, 3, 5]:
            await page.wait_for_timeout(1000)
            resultado = await page.evaluate("""() => {
                const g = (sel, attr) => document.querySelector(sel)?.getAttribute(attr) ?? null;

                return {
                    og_image:    g('meta[property="og:image"]', 'content'),
                    og_image_secure: g('meta[property="og:image:secure_url"]', 'content'),
                    schema_images: (() => {
                        const imgs = [];
                        for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
                            try {
                                const d = JSON.parse(s.textContent);
                                const obj = Array.isArray(d) ? d[0] : d;
                                if (obj?.image) imgs.push(JSON.stringify(obj.image).slice(0, 120));
                            } catch {}
                        }
                        return imgs;
                    })(),
                    imgs_src: Array.from(document.querySelectorAll('img'))
                        .map(i => ({
                            src:      (i.src || '').slice(0, 120),
                            data_src: (i.getAttribute('data-src') || '').slice(0, 120),
                            cls:      i.className.slice(0, 60),
                            alt:      (i.alt || '').slice(0, 60),
                        }))
                        .filter(i => i.src || i.data_src)
                        .slice(0, 20),
                };
            }""")

            og = resultado["og_image"]
            print(f"--- após {segundos}s ---")
            print(f"og:image         : {og}")
            print(f"og:image:secure  : {resultado['og_image_secure']}")
            print(f"schema.org images: {resultado['schema_images']}")
            print("imgs no DOM:")
            for img in resultado["imgs_src"]:
                print(f"  cls={img['cls']!r:50}  alt={img['alt']!r:40}")
                print(f"    src     : {img['src']}")
                print(f"    data-src: {img['data_src']}")
            print()

            if og:
                print("og:image encontrado — extrator genérico deveria funcionar após essa espera.")
                break
        else:
            print("og:image não apareceu — site usa outra estratégia para a imagem.")

        await page.close()


asyncio.run(main())
