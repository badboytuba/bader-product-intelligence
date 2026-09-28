/* Explicit isolated-clone functional tests. Run with BPI_SEARCH_BASE and
 * PLAYWRIGHT_MODULE; optional BPI_SEARCH_CREDENTIALS for admin catalog tests.
 * No product, source, classification or website writes. No AI calls. */
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const BASE = process.env.BPI_SEARCH_BASE;
assert(BASE && /^http:\/\/127\.0\.0\.1:\d+$/.test(BASE), 'Only an explicitly selected isolated clone is allowed.');
const OUT = process.env.BPI_SEARCH_OUT || '/tmp';
const report = {checks: [], widths: [], timings: [], errors: []};
(async () => {
    const browser = await chromium.launch({executablePath: process.env.CHROME || '/usr/bin/google-chrome', headless: true, args: ['--no-sandbox']});
    const context = await browser.newContext({locale: 'es-AR', serviceWorkers: 'block'});
    await context.route('**/*', route => new URL(route.request().url()).origin === BASE ? route.continue() : route.abort());
    const page = await context.newPage(); page.setDefaultTimeout(60000);
    page.on('pageerror', error => report.errors.push(error.message));
    const calls = [];
    page.on('request', request => { if (request.url().endsWith('/website/snippet/autocomplete')) calls.push(request.postDataJSON().params); });
    const input = page.locator('.bpi-header-search input');
    const rows = page.locator('.bpi-hs-row');
    async function search(query) {
        const start = Date.now();
        const response = page.waitForResponse(r => r.url().endsWith('/website/snippet/autocomplete') && r.request().postDataJSON().params.term === query);
        await input.fill(query); const data = await (await response).json();
        assert(!data.error); await page.waitForFunction(() => document.querySelector('.bpi-hs-list')?.getAttribute('aria-busy') !== 'true');
        report.timings.push({query, ms: Date.now() - start, count: data.result.results_count});
        return data.result;
    }
    try {
        await page.goto(BASE + '/', {waitUntil: 'networkidle', timeout: 180000});
        assert.equal(calls.length, 0); report.checks.push('no_autocomplete_on_open');
        for (const width of [1440,1024,768,360]) {
            await page.setViewportSize({width,height:1000});
            await input.waitFor({state:'visible'}); const box = await input.boundingBox(); assert(box.width > 200);
            const result = await search('17/4065-3'); assert(result.results[0].website_url.endsWith('-128'));
            assert.equal(await rows.count(), result.results.length);
            await page.waitForFunction(() => [...document.querySelectorAll('.bpi-hs-row img')].every(i => i.complete && i.naturalWidth > 0));
            assert((await rows.first().locator('img').count()) === 1);
            assert((await rows.first().innerText()).includes('17/4065-3'));
            const layout = await page.evaluate(() => ({overflow:document.documentElement.scrollWidth > innerWidth+1,popup:document.querySelector('.bpi-hs-results').getBoundingClientRect().toJSON()}));
            assert(!layout.overflow); assert(layout.popup.x >= 0 && layout.popup.right <= width+1);
            await page.screenshot({path:path.join(OUT,`search_${width}.png`)});
            report.widths.push({width,fieldWidth:box.width,thumbnails:true,overflow:false});
            await input.press('Escape'); assert(await page.locator('.bpi-hs-results').isHidden());
        }
        report.checks.push('four_widths_visible_field_images_sku_keyboard_escape');
        await page.setViewportSize({width:1440,height:1000});
        const result = await search('fres'); assert(/FRES/i.test(result.results[0].name), 'Direct name before category-only result');
        await input.press('ArrowUp'); assert.equal(await input.getAttribute('aria-activedescendant'), await rows.last().getAttribute('id'));
        await input.press('ArrowDown'); assert.equal(await input.getAttribute('aria-activedescendant'), await rows.first().getAttribute('id'));
        await input.fill('fresas para turbina'); assert.equal(await input.getAttribute('aria-activedescendant'), null);
        assert.equal(await rows.count() && !await page.locator('.bpi-hs-results').isHidden(), false);
        await page.locator('.bpi-hs-summary').filter({hasText:/productos/}).waitFor();
        report.checks.push('direct_identity_ranking_and_stale_keyboard_invalidation');
        await search('zzzz-no-result-9382'); assert.equal(await rows.count(), 0);
        assert((await page.locator('.bpi-hs-summary').innerText()).includes('Sin resultados'));
        await page.locator('.bpi-hs-clear').click(); assert.equal(await input.inputValue(), ''); assert(await page.locator('.bpi-hs-results').isHidden());
        report.checks.push('empty_results_and_clear');
        await search('17/4065-3');
        await Promise.all([page.waitForURL(/\/shop\?search=17/), page.locator('.bpi-hs-submit').click()]);
        assert.equal(new URL(page.url()).searchParams.get('search'),'17/4065-3');
        assert(await page.locator('#products_grid a[href*="-128"]').count());
        assert(await page.locator('[data-bpi-facet-form]').count());
        report.checks.push('native_shop_submission_and_facets');
        const termId = await page.locator('[data-bpi-term]').first().getAttribute('value');
        await page.goto(BASE + '/shop?search=17%2F4065-3&bpi_terms=' + termId, {waitUntil:'networkidle'});
        await search('fres');
        assert.deepEqual(calls.at(-1).options.bpiTermIds, [Number(termId)]);
        const all = new URL(await page.locator('.bpi-hs-all').getAttribute('href'));
        assert.equal(all.searchParams.get('bpi_terms'), termId); assert.equal(all.searchParams.get('search'), 'fres');
        report.checks.push('approved_filters_preserved_in_rpc_and_full_results_url');
        // Exact real mounted widget; native endpoint is replaced only here to
        // simulate reordered responses, malicious display data and failures.
        await page.route('**/website/snippet/autocomplete', async route => {
            const term = route.request().postDataJSON().params.term;
            if (term === 'error-test') return route.fulfill({status:500,body:'failed'});
            if (term === 'old-test') await new Promise(r => setTimeout(r,700));
            else await new Promise(r => setTimeout(r,40));
            const malicious = term === 'security-test';
            return route.fulfill({contentType:'application/json', body:JSON.stringify({result:{results_count:2,results:[
                {name: malicious ? '<img src=x onerror="window.bpiInjected=1">Texto seguro' : term, website_url:'/shop/fixture-128', default_code:'QA', image_url: malicious ? 'https://outside.invalid/tracker' : '/web/image/product.template/128/image_128', detail:'<b>$ 1,00</b>'},
                {name:'Unsafe target',website_url:'javascript:alert(1)',image_url:'data:text/html,abc'}]}})});
        });
        await input.fill('old-test'); await page.waitForTimeout(240); await input.fill('new-test');
        await rows.first().filter({hasText:'new-test'}).waitFor(); await page.waitForTimeout(900);
        assert((await rows.first().innerText()).includes('new-test'));
        report.checks.push('aborted_old_response_never_replaces_current_results');
        await search('security-test'); assert.equal(await rows.count(),1); assert.equal(await rows.locator('img').count(),0);
        assert.equal(await page.evaluate(()=>window.bpiInjected),undefined); assert((await rows.innerText()).includes('Texto seguro'));
        assert(new URL(await rows.first().getAttribute('href')).searchParams.get('bpi_terms') === termId);
        report.checks.push('untrusted_html_external_images_and_unsafe_urls_rejected');
        await input.fill('error-test'); await page.locator('.bpi-hs-summary').filter({hasText:'No pudimos'}).waitFor();
        assert.equal(await rows.count(),0); assert(await page.locator('.bpi-hs-all').isVisible());
        report.checks.push('error_falls_back_to_native_shop');
        if (process.env.BPI_SEARCH_CREDENTIALS) {
            const credentials = JSON.parse(fs.readFileSync(process.env.BPI_SEARCH_CREDENTIALS));
            const rpc = async (url,params) => { const r=await context.request.post(BASE+url,{data:{jsonrpc:'2.0',method:'call',params}}); const data=await r.json();assert(!data.error,url);return data.result; };
            assert((await rpc('/web/session/authenticate',{db:process.env.BPI_SEARCH_DB,login:credentials.login,password:credentials.password})).uid);
            const catalog=await rpc('/bader_product_intelligence/dashboard',{search:'17/4065-3',limit:8,page:1});
            assert(JSON.stringify(catalog).includes('17/4065-3'));
            await page.unroute('**/website/snippet/autocomplete');
            await page.goto(BASE+'/',{waitUntil:'networkidle'});await search('17/4065-3');assert(await input.isVisible());
            report.checks.push('authorized_catalog_and_header_same_exact_sku');
        }
        // Native form must exist and submit even without JavaScript.
        const plain = await browser.newContext({javaScriptEnabled:false}); const fallback=await plain.newPage();
        await fallback.goto(BASE+'/',{waitUntil:'domcontentloaded'});
        await fallback.locator('.bpi-header-search input').fill('17/4065-3');
        await Promise.all([fallback.waitForURL(/\/shop\?search=/),fallback.locator('.bpi-hs-submit').click()]);
        assert(new URL(fallback.url()).searchParams.get('search')==='17/4065-3');await plain.close();
        report.checks.push('server_rendered_no_javascript_fallback');
        assert.equal(report.errors.length,0);report.status='PASS'; console.log(JSON.stringify(report,null,2));
    } catch(error) {report.status='FAIL';report.failure=String(error);await page.screenshot({path:path.join(OUT,'search_failure.png')});throw error;}
    finally {fs.writeFileSync(path.join(OUT,'search_browser_results.json'),JSON.stringify(report,null,2));await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
