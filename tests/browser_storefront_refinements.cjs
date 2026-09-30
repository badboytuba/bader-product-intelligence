// Clone-only regression: never run this fixture writer against the team's QAS.
'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium,BASE,DB,dir,credentials}=require('./browser_variant_env.cjs');
const result={checks:[],errors:[],measurements:[]};
(async()=>{const browser=await chromium.launch({executablePath:'/usr/bin/google-chrome',headless:true,args:['--no-sandbox']});
const ctx=await browser.newContext({viewport:{width:1440,height:1080},serviceWorkers:'block'});
await ctx.route('**/*',r=>/^https?:$/.test(new URL(r.request().url()).protocol)&&new URL(r.request().url()).origin!==BASE?r.abort():r.continue());
const p=await ctx.newPage();p.setDefaultTimeout(90000);p.on('pageerror',e=>result.errors.push(e.message));
const admin=await browser.newContext();const rpc=async(route,params)=>{const r=await admin.request.post(BASE+route,{data:{jsonrpc:'2.0',method:'call',params}});const b=await r.json();assert(!b.error,route+': '+b.error?.data?.message);return b.result;};
const model=(model,method,args=[],kwargs={})=>rpc('/web/dataset/call_kw/'+model+'/'+method,{model,method,args,kwargs});
const url='/shop/unidad-dental-trekc-m2-1713?variant=1750';
const ready=async()=>{await p.waitForSelector('.carousel-indicators [aria-current]');await p.waitForFunction(()=>!document.querySelector('#product_detail')?.hasAttribute('aria-busy'));await p.waitForTimeout(700);};
const go=async()=>{await p.goto(BASE+url,{waitUntil:'domcontentloaded'});await ready();await p.locator('#wrapwrap').evaluate(e=>{e.style.scrollBehavior='auto';e.scrollTop=0});};
try{
 assert((await rpc('/web/session/authenticate',{db:DB,...credentials})).uid);
 await go();
 const search=p.locator('.bpi-header-search input[name="search"]');await search.fill('m2');await p.locator('.bpi-hs-results:not([hidden])').waitFor();
 const products=p.locator('header#top a').filter({hasText:/^\s*Productos\s*$/}).first();await products.hover();await p.locator('.o_mega_menu.show').waitFor();await p.waitForTimeout(250);
 assert(await p.locator('.bpi-hs-results').getAttribute('hidden')!==null,'autocomplete closes when menu opens');
 const hit=await p.evaluate(()=>{const r=document.querySelector('.bpi-header-search').getBoundingClientRect();return !!document.elementFromPoint(innerWidth/2,r.y+20)?.closest('.o_mega_menu');});assert(hit,'menu must cover search layer, not the reverse');
 const item=p.locator('.o_mega_menu.show a').filter({hasText:/Laboratorio Dental/}).first();await item.hover();assert(await item.isVisible());await p.screenshot({path:path.join(dir,'refined-menu.png')});await p.mouse.move(1380,720);await p.waitForTimeout(300);
 result.checks.push('native_hover_menu_reachable_above_search_and_closes_autocomplete');
 for(const width of [1440,1024,768,360]){
  await p.setViewportSize({width,height:1080});await p.locator('#wrapwrap').evaluate(e=>e.scrollTop=0);await p.waitForTimeout(600);
  await p.waitForFunction(()=>{const img=document.querySelector('.carousel-indicators li img');return img?.complete&&img.naturalWidth>0&&img.getBoundingClientRect().width>0;});
  const measure=await p.evaluate(()=>{const c=document.querySelector('.o_wsale_product_images'),r=document.querySelector('.carousel-indicators'),h=document.querySelector('.bpi-website-technical-description__header h2'),m=document.querySelector('.bpi-layout__main');return {width:innerWidth,overflow:document.querySelector('#wrapwrap').scrollWidth-innerWidth,follow:c.classList.contains('bpi-gallery-follow'),position:getComputedStyle(c).position,headingLeft:h.getBoundingClientRect().left,mainLeft:m.getBoundingClientRect().left,direction:getComputedStyle(r).flexDirection};});
  assert(measure.overflow<=1,JSON.stringify(measure));assert.equal(measure.follow,width>=992);assert(Math.abs(measure.headingLeft-measure.mainLeft)<=1,'heading aligned with description');
  assert.equal(measure.direction,width>=1200?'column':'row');
  if(width>=992){await p.locator('#wrapwrap').evaluate(e=>e.scrollTop=210);await p.waitForTimeout(400);const pos=await p.evaluate(()=>({top:document.querySelector('.o_wsale_product_images').getBoundingClientRect().top,header:document.querySelector('#top').getBoundingClientRect().bottom}));assert(Math.abs(pos.top-pos.header-16)<3,JSON.stringify(pos));
   await p.locator('#wrapwrap').evaluate(e=>e.scrollTop=1050);await p.waitForTimeout(350);assert(await p.evaluate(()=>document.querySelector('#o-carousel-product').getBoundingClientRect().bottom<=document.querySelector('#product_detail_main').getBoundingClientRect().bottom+1),'gallery stops at purchase row');}
  await p.locator('#wrapwrap').evaluate(e=>e.scrollTop=0);await p.waitForTimeout(500);await p.screenshot({path:path.join(dir,'refined-gallery-'+width+'.png')});result.measurements.push(measure);
 }
 result.checks.push('four_widths_bounded_desktop_sticky_mobile_static_and_heading_inset');
 await p.setViewportSize({width:1440,height:650});await p.waitForTimeout(500);assert(!await p.locator('.o_wsale_product_images').evaluate(e=>e.classList.contains('bpi-gallery-follow')),'short screen must not trap oversized card');
 await p.setViewportSize({width:1440,height:1080});await p.addStyleTag({content:'.carousel-indicators{scrollbar-width:auto!important}.carousel-indicators::-webkit-scrollbar{width:16px!important;height:16px!important}'});await p.waitForTimeout(300);
 const rail=p.locator('.carousel-indicators');assert(await rail.evaluate(e=>{const item=e.querySelector('li').getBoundingClientRect(),r=e.getBoundingClientRect();return item.right<=r.left+e.clientWidth&&item.left>=r.left+2;}),'classic scrollbar cannot cover card');
 await rail.locator('li').first().focus();await p.keyboard.press('End');await p.waitForTimeout(900);assert.equal(await rail.locator('li').last().getAttribute('aria-current'),'true');await p.keyboard.press('Home');await p.waitForTimeout(800);
 result.checks.push('classic_scrollbar_reserved_and_keyboard_thumbnails');
 const inputs=p.locator('#product_details input.js_variant_change[type="radio"]');await inputs.nth(1).check();await p.waitForFunction(()=>document.querySelector('#product_detail').dataset.bpiSelectedVariant==='2080'&&!document.querySelector('#product_detail').hasAttribute('aria-busy'));await p.waitForTimeout(600);
 assert(await p.locator('.o_wsale_product_images').evaluate(e=>e.classList.contains('bpi-gallery-follow')),'replacement gallery follows safely');
 await inputs.nth(0).check();await p.waitForFunction(()=>document.querySelector('#product_detail').dataset.bpiSelectedVariant==='1750'&&!document.querySelector('#product_detail').hasAttribute('aria-busy'));result.checks.push('native_variant_replacement_preserves_gallery_enhancement');
 // Actual OWL alignment control, preview and selective save. This product is
 // only the disposable DB copy; no fixture write goes to QAS.
 const action=await model('ir.actions.client','create',[{name:'BPI refinements isolated',tag:'bader_product_intelligence.action',context:JSON.stringify({active_id:1713})}]);
 const editor=await admin.newPage();editor.setDefaultTimeout(90000);editor.on('pageerror',e=>result.errors.push(e.message));await editor.goto(BASE+'/web#action='+action,{waitUntil:'domcontentloaded'});await editor.locator('[data-detail-section="content"]').click();await editor.getByRole('tab',{name:/Diseño Bader/}).click();
 const alignment=editor.getByLabel('Alineación del título de la descripción');await alignment.selectOption('center');await editor.getByRole('button',{name:'Vista previa',exact:true}).click();
 assert.equal(await editor.locator('.bpi-designer__heading-preview').evaluate(e=>getComputedStyle(e).textAlign),'center');
 const [saved]=await Promise.all([editor.waitForResponse(r=>r.url().endsWith('/save_content')),editor.locator('.bpi-workspace-section-heading button').click()]);await saved.finished();await go();assert.equal(await p.locator('.bpi-website-technical-description__header').evaluate(e=>getComputedStyle(e).textAlign),'center');
 await alignment.selectOption('left');const [restored]=await Promise.all([editor.waitForResponse(r=>r.url().endsWith('/save_content')),editor.locator('.bpi-workspace-section-heading button').click()]);await restored.finished();await editor.close();result.checks.push('real_editor_alignment_preview_selective_save_and_storefront');
 assert.equal(result.errors.length,0,JSON.stringify(result.errors));result.status='PASS';console.log('STOREFRONT_REFINEMENTS_PASS');
}catch(e){result.status='FAIL';result.failure=String(e);await p.screenshot({path:path.join(dir,'refinements-failure.png')}).catch(()=>{});throw e;}finally{fs.writeFileSync(path.join(dir,'refinements_certificate.json'),JSON.stringify(result,null,2));await browser.close();}
})().catch(e=>{console.error(String(e.stack).split(credentials.password).join('[REDACTED]'));process.exitCode=1});
