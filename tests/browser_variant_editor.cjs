// Destructive clone-only fixtures. Never use a team QAS or production database.
'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium,BASE,DB,dir,credentials}=require('./browser_variant_env.cjs');
const creds=credentials,fixture=JSON.parse(fs.readFileSync(path.join(dir,'variant_browser_fixture.json')));
const result={checks:[],errors:[],generationCalls:[]};result.checks.push=function(...v){console.log('CHECK',...v);return Array.prototype.push.apply(this,v);};
(async()=>{
 const browser=await chromium.launch({executablePath:'/usr/bin/google-chrome',headless:true,args:['--no-sandbox']});
 const ctx=await browser.newContext({viewport:{width:1440,height:1100},serviceWorkers:'block'});
 await ctx.route('**/*',route=>{const u=new URL(route.request().url());return /^https?:$/.test(u.protocol)&&u.origin!==BASE?route.abort():route.continue();});
 const rpc=async(route,params)=>{const r=await ctx.request.post(BASE+route,{data:{jsonrpc:'2.0',method:'call',params}});const b=await r.json();assert(!b.error,route+': '+(b.error?.data?.message||''));return b.result;};
 const model=(model,method,args=[],kwargs={})=>rpc('/web/dataset/call_kw/'+model+'/'+method,{model,method,args,kwargs});
 const bpi=(route,params)=>rpc('/bader_product_intelligence/'+route,params);
 const page=await ctx.newPage();page.setDefaultTimeout(90000);page.on('pageerror',e=>result.errors.push(e.message));
 page.on('request',r=>{if(/bader_product_intelligence\/.*(?:generate|enqueue|analyze|image\/)/.test(r.url()))result.generationCalls.push(r.url().split('?')[0]);});
 try {
  assert((await rpc('/web/session/authenticate',{db:DB,...creds})).uid);
  const actions=await model('ir.actions.client','search',[[['name','=','BPI variant browser isolation']]]);
  const action=actions[0]||await model('ir.actions.client','create',[{name:'BPI variant browser isolation',tag:'bader_product_intelligence.action',context:JSON.stringify({active_id:fixture.id})}]);
  await page.goto(BASE+'/web#action='+action,{waitUntil:'domcontentloaded'});
  const selector=page.locator('#bpi-workspace-variant');await selector.waitFor();
  const high=fixture.variants[0].id,starter=fixture.variants[1].id;
  const original=(await bpi('data',{product_tmpl_id:fixture.id,product_variant_id:high})).variantContent;
  const select=async id=>{const [r]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/bader_product_intelligence/data')),selector.selectOption(String(id||''))]);await r.finished();await page.waitForTimeout(150);await page.waitForFunction(id=>document.querySelector('#bpi-workspace-variant')?.value===String(id||'')&&!document.querySelector('#bpi-workspace-variant').disabled,id);};
  const save=async()=>{const [r]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/variant_content/save')),page.locator('.bpi-workspace-section-heading button').click()]);await r.finished();await page.waitForFunction(()=>!document.querySelector('#bpi-workspace-variant').disabled);};
  await select(high);await page.locator('[data-detail-section="seo"]').click();
  const title=page.locator('input[maxlength="60"]');await title.fill('Borrador High sin guardar');
  await select(starter);assert.equal(await title.inputValue(),'Edición SEO 1');await title.fill('Borrador Starter sin guardar');
  await select(high);assert.equal(await title.inputValue(),'Borrador High sin guardar');
  assert.equal((await bpi('data',{product_tmpl_id:fixture.id,product_variant_id:high})).variantContent.values.seoTitle,original.values.seoTitle);
  result.checks.push('real_dom_two_variant_drafts_no_automatic_save');
  await save();
  await page.waitForTimeout(1000);
  assert.equal((await bpi('data',{product_tmpl_id:fixture.id,product_variant_id:high})).variantContent.values.seoTitle,'Borrador High sin guardar');
  assert.equal((await bpi('data',{product_tmpl_id:fixture.id,product_variant_id:starter})).variantContent.values.seoTitle,'Edición SEO 1');
  result.checks.push('real_dom_save_only_selected_variant');
  await title.fill('');await save();await page.waitForTimeout(1000);
  const empty=(await bpi('data',{product_tmpl_id:fixture.id,product_variant_id:high})).variantContent;
  assert(empty.overridden.includes('seoTitle'));assert.equal(empty.values.seoTitle,'');
  await page.locator('.bpi-variant-workspace__field').filter({hasText:'Título SEO'}).getByRole('button',{name:'Volver a heredar',exact:true}).click();
  await save();await page.waitForTimeout(1000);
  assert(!(await bpi('data',{product_tmpl_id:fixture.id,product_variant_id:high})).variantContent.overridden.includes('seoTitle'));
  result.checks.push('real_dom_explicit_empty_and_return_to_inheritance');
  assert((await page.locator('input[readonly]').inputValue()).includes('?variant='+high));
  await page.locator('[data-detail-section="chat"]').click();
  const [opened]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/content_studio/open')),page.getByRole('button',{name:/Abrir Nancy AI Studio de esta edición/}).click()]);await opened.finished();await page.waitForTimeout(200);
  await page.locator('.bpi-studio').waitFor();
  result.checks.push('variant_chat_enters_own_studio_without_generation');
  await page.locator('.bpi-studio__close').click();
  await page.locator('.bpi-studio').waitFor({state:'hidden'});
  await page.locator('[data-detail-section="seo"]').click();
  for(const width of [360,768,1024,1440]){
   await page.setViewportSize({width,height:1000});await page.waitForTimeout(250);
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'backend overflow '+width);
   await page.screenshot({path:path.join(dir,'variant-workspace-'+width+'.png'),fullPage:true});
  }
  result.checks.push('real_editor_four_viewports');
  const current=(await bpi('data',{product_tmpl_id:fixture.id,product_variant_id:high})).variantContent;
  await bpi('variant_content/save',{product_tmpl_id:fixture.id,product_variant_id:high,base_revision:current.baseRevision,revision:current.revision,context_revision:current.contextRevision,changes:{seoTitle:original.values.seoTitle},inherit:[]});
  assert.equal(result.generationCalls.length,0);assert.equal(result.errors.length,0,JSON.stringify(result.errors));result.status='PASS';console.log('VARIANT_WORKSPACE_PASS');
 }catch(e){result.status='FAIL';result.failure=String(e).split(creds.password).join('[REDACTED]');await page.screenshot({path:path.join(dir,'workspace-failure.png'),fullPage:true}).catch(()=>{});throw e;}
 finally{fs.writeFileSync(path.join(dir,'workspace_browser_results.json'),JSON.stringify(result,null,2));await browser.close();}
})().catch(e=>{console.error(String(e.stack).split(creds.password).join('[REDACTED]'));process.exitCode=1;});
