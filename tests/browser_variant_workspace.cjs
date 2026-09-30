// Destructive clone-only fixtures. Never use a team QAS or production database.
'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium,BASE,DB,dir,credentials}=require('./browser_variant_env.cjs');
const result={checks:[],errors:[]};
(async()=>{
 const browser=await chromium.launch({executablePath:'/usr/bin/google-chrome',headless:true,args:['--no-sandbox']});
 const admin=await browser.newContext(),ctx=await browser.newContext({viewport:{width:1440,height:1100},serviceWorkers:'block'});
 await ctx.route('**/*',route=>{const u=new URL(route.request().url());return /^https?:$/.test(u.protocol)&&u.origin!==BASE?route.abort():route.continue();});
 const rpc=async(route,params)=>{const r=await admin.request.post(BASE+route,{data:{jsonrpc:'2.0',method:'call',params}});const b=await r.json();assert(!b.error,'RPC '+route+' '+(b.error?.data?.message||''));return b.result;};
 const model=(model,method,args=[],kwargs={})=>rpc('/web/dataset/call_kw/'+model+'/'+method,{model,method,args,kwargs});
 const bpi=(route,params)=>rpc('/bader_product_intelligence/'+route,params);
 const page=await ctx.newPage();page.setDefaultTimeout(90000);page.on('pageerror',e=>result.errors.push(e.message));
 try {
  assert((await rpc('/web/session/authenticate',{db:DB,...credentials})).uid);
  await model('website','write',[[1],{bpi_premium_storefront_enabled:true,bpi_premium_footer_html:'<p>Validación aislada de variantes — no es el QAS del equipo</p>',bpi_premium_footer_legal_name:'VALIDACIÓN AISLADA'}]);
  let fixture;
  const fixturePath=path.join(dir,'variant_browser_fixture.json');
  if(fs.existsSync(fixturePath)) fixture=JSON.parse(fs.readFileSync(fixturePath));
  else {
   const aid=await model('product.attribute','create',[{name:'Edición de validación BPI'}]);
   const values=await model('product.attribute.value','create',[[{name:'High test',attribute_id:aid},{name:'Starter test',attribute_id:aid}]]);
   const id=await model('product.template','create',[{name:'BPI VALIDACIÓN VARIANTES',sale_ok:true,is_published:true,website_id:1,list_price:100,bpi_ai_generated_description:'<p>Base común intacta</p>',bpi_technical_description:'<p>Base larga</p>',attribute_line_ids:[[0,0,{attribute_id:aid,value_ids:[[6,0,values]]}]]}]);
   const variants=await model('product.product','search_read',[[['product_tmpl_id','=',id]],['id','product_template_attribute_value_ids']],{order:'id'});
   for(let i=0;i<variants.length;i++) {
    await model('product.product','write',[[variants[i].id],{default_code:'BPI-VARIANT-TEST-'+i}]);
    await model('product.template.attribute.value','write',[variants[i].product_template_attribute_value_ids,{price_extra:i*20}]);
   }
   const [product]=await model('product.template','read',[[id],['website_url']]);fixture={id,variants,url:product.website_url};
   fs.writeFileSync(fixturePath,JSON.stringify(fixture));
  }
  const pixels=["iVBORw0KGgoAAAANSUhEUgAAAKAAAAB4CAIAAAD6wG44AAABMElEQVR4nO3RwQnAIADAwFpcyq/7D+UUIoS7CQIZc+2Prv91AHcZHGdwnMFxBscZHGdwnMFxBscZHGdwnMFxBscZHGdwnMFxBscZHGdwnMFxBscZHGdwnMFxBscZHGdwnMFxBscZHGdwnMFxBscZHGdwnMFxBscZHGdwnMFxBscZHGdwnMFxBscZHGdwnMFxBscZHGdwnMFxBscZHGdwnMFxBscZHGdwnMFxBscZHGdwnMFxBscZHGdwnMFxBscZHGdwnMFxBscZHGdwnMFxBscZHGdwnMFxBscZHGdwnMFxBscZHGdwnMFxBscZHGdwnMFxBscZHGdwnMFxBscZHGdwnMFxBscZHGdwnMFxBscZHGdwnMFxBscZHGdwnMFxBscZHGdwnMFxBscZHGdw3AF3ygFv7Jdm1gAAAABJRU5ErkJggg==", "iVBORw0KGgoAAAANSUhEUgAAAKAAAAB4CAIAAAD6wG44AAABL0lEQVR4nO3RAQkAIQDAwPf72M2y9jGFCOMuwWBj7fnR9b8O4C6D4wyOMzjO4DiD4wyOMzjO4DiD4wyOMzjO4DiD4wyOMzjO4DiD4wyOMzjO4DiD4wyOMzjO4DiD4wyOMzjO4DiD4wyOMzjO4DiD4wyOMzjO4DiD4wyOMzjO4DiD4wyOMzjO4DiD4wyOMzjO4DiD4wyOMzjO4DiD4wyOMzjO4DiD4wyOMzjO4DiD4wyOMzjO4DiD4wyOMzjO4DiD4wyOMzjO4DiD4wyOMzjO4DiD4wyOMzjO4DiD4wyOMzjO4DiD4wyOMzjO4DiD4wyOMzjO4DiD4wyOMzjO4DiD4wyOMzjO4DiD4wyOMzjO4DiD4wyOMzjO4DiD4wyOMzjO4DiD4wyOMzjO4DiD4wyOO4fXAmImEl3XAAAAAElFTkSuQmCC"];
  for(let n=0;n<fixture.variants.length;n++) await model('product.product','write',[[fixture.variants[n].id],{image_variant_1920:pixels[n]}]);
  const nativeImages=await model('product.image','search',[[['product_variant_id','=',fixture.variants[0].id],['name','=','Galería High test']]]);
  const nativeImage=nativeImages[0] || await model('product.image','create',[{name:'Galería High test',product_variant_id:fixture.variants[0].id,image_1920:pixels[0]}]);
  await model('product.product','write',[[fixture.variants[1].id],{image_variant_1920:false}]);
  const privateImages=await model('bpi.product.image','search',[[['product_tmpl_id','=',fixture.id],['name','=','BPI ref Starter test']]]);
  const privateImage=privateImages[0] || await model('bpi.product.image','create',[{name:'BPI ref Starter test',product_tmpl_id:fixture.id,image_1920:pixels[1],mime_type:'image/png',state:'approved'}]);
  for(let i=0;i<fixture.variants.length;i++) {
   const v=fixture.variants[i].id,data=await bpi('data',{product_tmpl_id:fixture.id,product_variant_id:v}),scope=data.variantContent;
   const changes={description:'<p>Descripción exclusiva '+i+'</p>',technicalDescription:'<p>Detalle exclusivo '+i+'</p>',seoTitle:'Edición SEO '+i,seoDescription:'Metadatos propios '+i,gallery:[i===0?'odoo:'+nativeImage:'bpi:'+privateImage]};
   await bpi('variant_content/save',{product_tmpl_id:fixture.id,product_variant_id:v,base_revision:scope.baseRevision,revision:scope.revision,context_revision:scope.contextRevision,changes,inherit:[]});
  }
  const high=fixture.variants[0],starter=fixture.variants[1];
  const original=(await bpi('data',{product_tmpl_id:fixture.id,product_variant_id:high.id})).variantContent;
  const envelope={product_tmpl_id:fixture.id,product_variant_id:high.id,base_revision:original.baseRevision,revision:original.revision,context_revision:original.contextRevision,inherit:[]};
  const writes=await Promise.all(['Operador A','Operador B'].map(title=>admin.request.post(BASE+'/bader_product_intelligence/variant_content/save',
   {data:{jsonrpc:'2.0',method:'call',params:{...envelope,changes:{seoTitle:title}}}}).then(r=>r.json())));
  assert.equal(writes.filter(r=>!r.error).length,1);assert.equal(writes.filter(r=>r.error).length,1);
  const revised=(await bpi('data',{product_tmpl_id:fixture.id,product_variant_id:high.id})).variantContent;
  await bpi('variant_content/save',{...envelope,revision:revised.revision,context_revision:revised.contextRevision,changes:{seoTitle:'Edición SEO 0'}});
  result.checks.push('two_operators_one_wins_other_preserves_revision_conflict');

  const highUrl=BASE+fixture.url+'?variant='+high.id,starterUrl=BASE+fixture.url+'?variant='+starter.id;
  for(const [index,url] of [[0,highUrl],[1,starterUrl]]) {
   const response=await ctx.request.get(url);assert.equal(response.status(),200);const html=await response.text();
   assert(html.includes('Edición SEO '+index));assert(html.includes('Descripción exclusiva '+index));assert(!html.includes('Descripción exclusiva '+(1-index)));
   assert(html.includes('data-bpi-product-group'));assert(new RegExp('rel="canonical"[^>]*variant='+fixture.variants[index].id+'|variant='+fixture.variants[index].id+'[^>]*rel="canonical"').test(html));result.checks.push('server_render_'+index);
  }
  assert.equal((await ctx.request.get(BASE+fixture.url+'?variant=99999999')).status(),404);result.checks.push('invalid_variant_404');
  const searchResponse=await ctx.request.get(BASE+'/shop?search=BPI-VARIANT-TEST-1');assert.equal(searchResponse.status(),200);
  const searchHtml=await searchResponse.text();assert(searchHtml.includes('?variant='+starter.id));
  result.checks.push('grouped_sku_search_links_matching_edition');

  await page.goto(highUrl,{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>!document.querySelector('#product_detail')?.hasAttribute('aria-busy'));
  await page.locator('.bpi-variant-short').waitFor();
  assert((await page.locator('.bpi-variant-short').innerText()).includes('exclusiva 0'));
  assert(await page.locator('.o_wsale_product_images img[src*="product.image/'+nativeImage+'/"]').count());
  const firstPrice=await page.locator('#product_details .oe_price').first().innerText();
  await page.locator(`input.js_variant_change[value="${starter.product_template_attribute_value_ids[0]}"]`).check();
  await page.waitForFunction(id=>document.querySelector('#product_detail')?.dataset.bpiSelectedVariant===String(id)&&!document.querySelector('#product_detail').hasAttribute('aria-busy'),starter.id);
  assert((await page.locator('.bpi-variant-short').innerText()).includes('exclusiva 1'));
  assert.notEqual(await page.locator('#product_details .oe_price').first().innerText(),firstPrice);
  assert.equal(Number(await page.locator('input.product_id').first().inputValue()),starter.id);assert(new URL(page.url()).searchParams.get('variant')===String(starter.id));
  assert(await page.locator('.o_wsale_product_images img[src*="/variant_gallery/'+fixture.id+'/'+starter.id+'/'+privateImage+'"]').count());
  assert.equal(await page.locator('.o_wsale_product_images img[src*="product.image/'+nativeImage+'/"]').count(),0);result.checks.push('native_gallery_custom_reference_replaced_without_sibling_leak');
  assert.equal(await page.title(),'Edición SEO 1');result.checks.push('native_switch_price_identity_copy_seo');
  let imageUrl=await page.locator('.product_detail_img[src*="/variant_gallery/"]').first().getAttribute('src');
  const publicImage=await ctx.request.get(BASE+imageUrl);assert.equal(publicImage.status(),200);assert(publicImage.headers()['content-type'].startsWith('image/'));
  assert.equal(publicImage.headers()['x-content-type-options'],'nosniff');
  const privateDirect=await ctx.request.get(BASE+'/web/image/bpi.product.image/'+privateImage+'/image_1920');
  assert(!(await privateDirect.body()).equals(await publicImage.body()),'private generic route must not expose the image');
  assert.equal((await ctx.request.get(BASE+imageUrl.replace('/'+starter.id+'/'+privateImage,'/'+high.id+'/'+privateImage))).status(),404);
  assert.equal((await ctx.request.get(BASE+imageUrl.replace('size=1024','size=900000'))).status(),404);
  assert.equal((await ctx.request.get(BASE+imageUrl.replace(/r=[^&]+/,'r=0-0'))).status(),404);
  result.checks.push('saved_private_reference_public_only_in_own_revision_and_variant');
  const galleryState=(await bpi('data',{product_tmpl_id:fixture.id,product_variant_id:starter.id})).variantContent;
  const saveGallery=async(scope,gallery)=>bpi('variant_content/save',{product_tmpl_id:fixture.id,product_variant_id:starter.id,
    base_revision:scope.baseRevision,revision:scope.revision,context_revision:scope.contextRevision,changes:{gallery},inherit:[]});
  await saveGallery(galleryState,[]);
  assert.equal((await ctx.request.get(BASE+imageUrl)).status(),404,'removed reference must immediately stop public delivery');
  assert(await model('bpi.product.image','search_count',[[['id','=',privateImage]]]),'original image must remain');
  await saveGallery((await bpi('data',{product_tmpl_id:fixture.id,product_variant_id:starter.id})).variantContent,['bpi:'+privateImage]);
  result.checks.push('removed_gallery_reference_revokes_public_access_without_deleting_original');


  await page.goBack({waitUntil:'domcontentloaded'});await page.waitForFunction(id=>document.querySelector('#product_detail')?.dataset.bpiSelectedVariant===String(id),high.id);
  assert((await page.locator('.bpi-variant-short').innerText()).includes('exclusiva 0'));result.checks.push('history_back');
  // Delay one old response until a newer edition has already won.
  let releaseSlow, signalSlow; const slowSeen = new Promise(resolve=>signalSlow=resolve);
  let slowOnce=true;
  await page.route('**/*get_combination_info*', async route=>{
   const params=route.request().postDataJSON()?.params || {};
   const response=await route.fetch();
   if(slowOnce && params.combination?.includes(starter.product_template_attribute_value_ids[0])) {
    slowOnce=false;signalSlow();await new Promise(resolve=>releaseSlow=resolve);
   }
   await route.fulfill({response});
  });
  await page.locator(`input.js_variant_change[value="${starter.product_template_attribute_value_ids[0]}"]`).check();
  await slowSeen;
  await page.locator(`input.js_variant_change[value="${high.product_template_attribute_value_ids[0]}"]`).check();
  await page.waitForFunction(id=>document.querySelector('#product_detail')?.dataset.bpiSelectedVariant===String(id)&&!document.querySelector('#product_detail').hasAttribute('aria-busy'),high.id);
  releaseSlow();await page.waitForTimeout(1200);
  assert((await page.locator('.bpi-variant-short').innerText()).includes('exclusiva 0'));
  assert.equal(Number(await page.locator('input.product_id').first().inputValue()),high.id);
  result.checks.push('late_response_cannot_mix_price_copy_or_cart_sku');
  await page.unroute('**/*get_combination_info*');
  let failOnce=true;
  await page.route('**/*get_combination_info*', route=>{if(failOnce){failOnce=false;return route.abort('failed');}return route.continue();});
  await page.locator(`input.js_variant_change[value="${starter.product_template_attribute_value_ids[0]}"]`).check();
  await page.locator('.bpi-variant-status').waitFor();
  assert(await page.locator('#add_to_cart').evaluate(el=>el.classList.contains('disabled')));
  assert.equal(Number(await page.locator('input.product_id').first().inputValue()),high.id);
  await page.getByRole('button',{name:'Reintentar',exact:true}).click();
  await page.waitForFunction(id=>document.querySelector('#product_detail')?.dataset.bpiSelectedVariant===String(id)&&!document.querySelector('#product_detail').hasAttribute('aria-busy'),starter.id);
  assert((await page.locator('.bpi-variant-short').innerText()).includes('exclusiva 1'));
  assert.equal(await page.locator('.bpi-variant-status').count(),0);
  result.checks.push('transport_failure_blocks_wrong_sku_and_manual_retry_recovers');
  await page.unroute('**/*get_combination_info*');
  for(const width of [360,768,1024,1440]) {
   await page.setViewportSize({width,height:1000});await page.waitForTimeout(200);
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'overflow '+width);
   await page.screenshot({path:path.join(dir,'variant-public-'+width+'.png'),fullPage:true});
  }
  result.checks.push('four_viewports_no_horizontal_overflow');
  await page.setViewportSize({width:1440,height:1000});
  result.beforeCart=await page.evaluate(()=>({busy:document.querySelector('#product_detail').hasAttribute('aria-busy'),error:document.querySelector('#product_detail').dataset.bpiVariantError||'',sku:document.querySelector('input.product_id')?.value,disabled:document.querySelector('#add_to_cart').className}));
  const [cartResponse]=await Promise.all([page.waitForResponse(r=>/\/shop\/cart\/update(?:_json)?(?:\?|$)/.test(r.url()),{timeout:90000}),page.locator('#add_to_cart').click()]);
  result.cartHttpStatus=cartResponse.status();await cartResponse.finished();await page.waitForTimeout(700);
  await page.goto(BASE+'/shop/cart',{waitUntil:'domcontentloaded'});
  assert((await page.locator('body').innerText()).includes('Starter test'));
  const lines=await model('sale.order.line','search_read',[[['product_id','=',starter.id]],['product_id','product_uom_qty','price_unit']],{order:'id desc',limit:1});
  assert.equal(lines.length,1);assert.equal(lines[0].product_id[0],starter.id);assert(lines[0].product_uom_qty>0);
  result.checks.push('native_cart_contains_selected_sku');
  const common=await bpi('data',{product_tmpl_id:fixture.id});assert.equal(common.seoData.aiGeneratedDescriptionHtml,'<p>Base común intacta</p>');result.checks.push('common_unchanged');
  const currentHtml=await (await ctx.request.get(starterUrl)).text();
  imageUrl=currentHtml.match(/src="([^" ]*\/variant_gallery\/[^" ]+)"/)[1].replace(/&amp;/g,'&');
  assert.equal((await ctx.request.get(BASE+imageUrl)).status(),200,'current image works before feature is disabled');
  await model('website','write',[[1],{bpi_variant_content_enabled:false}]);
  try {
   const legacy=await ctx.request.get(starterUrl);assert.equal(legacy.status(),200);const html=await legacy.text();
   assert(html.includes('Base común intacta'));assert(!html.includes('data-bpi-variant-workspace='));
   assert.equal((await ctx.request.get(BASE+imageUrl)).status(),404);
  } finally {await model('website','write',[[1],{bpi_variant_content_enabled:true}]);}
  const [secondWebsite]=await model('website','read',[[2],['bpi_variant_content_enabled','bpi_premium_storefront_enabled']]);
  assert.equal(secondWebsite.bpi_variant_content_enabled,false);assert.equal(secondWebsite.bpi_premium_storefront_enabled,false);
  result.checks.push('premium_storefront_combined_and_feature_off_legacy_and_second_site_flags');
  assert.equal(result.errors.length,0,JSON.stringify(result.errors));result.status='PASS';console.log('VARIANT_BROWSER_PASS');
 } catch(e) {result.status='FAIL';result.failure=String(e).split(credentials.password).join('[REDACTED]');await page.screenshot({path:path.join(dir,'variant-browser-failure.png'),fullPage:true}).catch(()=>{});throw e;}
 finally {fs.writeFileSync(path.join(dir,'variant_browser_results.json'),JSON.stringify(result,null,2));await browser.close();}
})().catch(e=>{console.error(String(e.stack).split(credentials.password).join('[REDACTED]'));process.exitCode=1;});
