'use strict';
// Local Chromium/OWL regression. Odoo services are mocked; never authenticates,
// contacts a server, saves real products, or substitutes for QAS certification.
// Supply local Odoo owl.js, QUnit JS and the installed Playwright module via env.
const fs = require('node:fs'), path = require('node:path'), http = require('node:http');
const assert = require('node:assert/strict'), crypto = require('node:crypto');
for (const name of ['BPI_OWL_FILE', 'BPI_QUNIT_FILE', 'BPI_PLAYWRIGHT_MODULE', 'BPI_TEST_ARTIFACTS'])
    assert(process.env[name], `Required environment variable: ${name}`);
const {chromium} = require(process.env.BPI_PLAYWRIGHT_MODULE);
const filter = process.env.BPI_TEST_FILTER ?? 'copy-only';
const expectedTests = Number(process.env.BPI_EXPECTED_TESTS || 5);
if (filter !== 'copy-only') assert(process.env.BPI_ACTION_HOOK_FILE, 'Full suite requires the native Odoo action hook');
const addon = path.resolve(__dirname, '..'), out = path.resolve(process.env.BPI_TEST_ARTIFACTS);
fs.mkdirSync(out, {recursive: true, mode: 0o700});
const read = relative => fs.readFileSync(path.join(addon, relative), 'utf8');
const strip = source => source.replace(/^import[\s\S]*?from\s+["'][^"']+["'];\s*/mg, '').replace(/^export /mg, '');
const sourcePaths = ['static/src/js/content_studio.js', 'static/src/js/variant_workspace.js',
    'static/src/js/product_intelligence_action.js', 'static/tests/product_intelligence_tests.js',
    'static/tests/content_studio_tests.js'];
const report = {mode: 'Local actual OWL/Chromium; mocked Odoo services; no deployment', status: 'RUNNING',
    sourceHashes: Object.fromEntries(sourcePaths.map(file => [file, crypto.createHash('sha256').update(read(file)).digest('hex')])),
    errors: [], blockedNetwork: []};
const server = http.createServer((req, res) => {
    res.setHeader('Content-Type', 'text/html');
    res.end('<!doctype html><html><head><meta charset="utf-8"></head><body><div id="qunit"></div><div id="qunit-fixture"></div></body></html>');
});
(async () => {
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    const base = `http://127.0.0.1:${server.address().port}`;
    const browser = await chromium.launch({executablePath: process.env.BPI_CHROME_BINARY || '/usr/bin/google-chrome',
        headless: true, args: ['--no-sandbox']});
    const context = await browser.newContext({serviceWorkers: 'block'});
    await context.route('**/*', route => {
        if (new URL(route.request().url()).origin === base) return route.continue();
        report.blockedNetwork.push(new URL(route.request().url()).origin); return route.abort();
    });
    const page = await context.newPage();
    page.on('pageerror', error => report.errors.push(error.message));
    try {
        await page.goto(base);
        await page.addScriptTag({path: process.env.BPI_OWL_FILE});
        await page.evaluate(() => { window.QUnit = {config: {autostart: false}}; });
        await page.addScriptTag({path: process.env.BPI_QUNIT_FILE});
        await page.evaluate(filter => {
            QUnit.config.autostart = false; QUnit.config.filter = filter; QUnit.config.testTimeout = 20000;
            window.registry = {category: () => ({add() {}})};
            window.useService = name => owl.useEnv().services[name];
            window.useSetupAction = () => {}; // Navigation is exercised by the real action methods.
            window.result = {tests: [], failures: []};
            QUnit.log(data => { if (!data.result) result.failures.push({message: data.message, actual: String(data.actual), expected: String(data.expected)}); });
            QUnit.testDone(data => result.tests.push({name: data.name, failed: data.failed}));
            QUnit.done(data => { result.done = data; });
        }, filter);
        if (process.env.BPI_ACTION_HOOK_FILE) {
            await page.addScriptTag({content: `(() => {const {onMounted, useComponent, useEffect, useExternalListener} = owl;
                ${strip(fs.readFileSync(process.env.BPI_ACTION_HOOK_FILE, 'utf8'))}
                window.actionHook = {CallbackRecorder}; window.useSetupAction = useSetupAction;})();`});
        }
        await page.addScriptTag({content: `(() => {const {markup, Component, useRef, onMounted, onPatched} = owl;
            ${strip(read(sourcePaths[0]))}
            window.studio = {contentStudioMethods, emptyContentStudio, defaultDescriptionLayout, StudioRichEditor};})();`});
        await page.addScriptTag({content: `(() => {${strip(read(sourcePaths[1]))}
            window.variantWorkspaceMethods = variantWorkspaceMethods;})();`});
        await page.addScriptTag({content: `(() => {const {Component, onWillStart, onWillUnmount, onMounted, onPatched, useState, useRef} = owl;
            const {contentStudioMethods, emptyContentStudio, StudioRichEditor} = window.studio;
            ${strip(read(sourcePaths[2]))}
            window.actionExports = {ProductIntelligenceAction, canDeleteGalleryImage, competitorComparablePriceUsd, productEffectivePriceRange};})();`});
        await page.evaluate(docs => {
            window.templates = new DOMParser().parseFromString('<templates>' + docs.map(source =>
                source.replace(/<\?xml[^>]+>/, '').replace(/<\/?templates[^>]*>/g, '')).join('\n') + '</templates>', 'text/xml');
            // Match native web/tests/setup.js resource suppression. This is test
            // template preparation only, never a source/public template change.
            for (const image of templates.querySelectorAll('img')) {
                for (const key of ['src', 'alt', 't-att-src', 't-att-alt']) {
                    if (!image.hasAttribute(key)) continue;
                    image.setAttribute(key.replace(/(src|alt)$/, 'data-$1'), image.getAttribute(key));
                    image.removeAttribute(key);
                }
            }
        }, ['product_intelligence_templates.xml', 'content_studio.xml'].map(file => read(`static/src/xml/${file}`)));
        await page.addScriptTag({content: `(() => {const {App} = owl;
            const CallbackRecorder = window.actionHook?.CallbackRecorder;
            const {ProductIntelligenceAction, canDeleteGalleryImage, competitorComparablePriceUsd, productEffectivePriceRange} = window.actionExports;
            ${strip(read(sourcePaths[3]))}})();`});
        await page.addScriptTag({content: `(() => {const {App} = owl; const {ProductIntelligenceAction} = window.actionExports;
            const {emptyContentStudio, defaultDescriptionLayout, StudioRichEditor} = window.studio;
            ${strip(read(sourcePaths[4]))}})();`});
        await page.evaluate(() => QUnit.start());
        await page.waitForFunction(() => result.done, null, {timeout: 120000});
        Object.assign(report, await page.evaluate(() => result));
        assert.equal(report.tests.length, expectedTests, 'Exact test count');
        assert.equal(report.done.failed, 0, 'No regression assertions fail');
        assert.equal(report.errors.length, 0, 'No browser exceptions');
        assert.equal(report.blockedNetwork.length, 0, 'No external/application calls');
        report.status = 'PASS';
    } catch (error) {
        report.status = 'FAIL'; report.failure = error.message;
        Object.assign(report, await page.evaluate(() => window.result || {}).catch(() => ({})));
        process.exitCode = 1;
    } finally {
        fs.writeFileSync(path.join(out, 'copy_drafts_certificate.json'), JSON.stringify(report, null, 2), {mode: 0o600});
        await browser.close(); await new Promise(resolve => server.close(resolve));
    }
    console.log(JSON.stringify({status: report.status, tests: report.tests?.length, assertions: report.done?.total,
        failures: report.failures, errors: report.errors}));
})().catch(error => { server.close(); console.error(error.message); process.exitCode = 1; });
