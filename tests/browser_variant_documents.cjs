// Destructive clone-only fixtures. Never use a team QAS or production database.
'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium,BASE,DB,dir,credentials}=require('./browser_variant_env.cjs');
const creds=credentials,fixture=JSON.parse(fs.readFileSync(path.join(dir,'variant_browser_fixture.json')));
const result={checks:[]};
const pdf=()=>{let data='%PDF-1.4\n',offsets=[0];const objs=['<< /Type /Catalog /Pages 2 0 R >>','<< /Type /Pages /Kids [3 0 R] /Count 1 >>','<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] /Resources << >> >>'];for(let i=0;i<objs.length;i++){offsets.push(Buffer.byteLength(data));data+=(i+1)+' 0 obj\n'+objs[i]+'\nendobj\n';}const xref=Buffer.byteLength(data);data+='xref\n0 4\n0000000000 65535 f \n'+offsets.slice(1).map(v=>String(v).padStart(10,'0')+' 00000 n \n').join('')+'trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n'+xref+'\n%%EOF\n';return Buffer.from(data).toString('base64');};
(async()=>{const browser=await chromium.launch({executablePath:'/usr/bin/google-chrome',headless:true,args:['--no-sandbox']});const admin=await browser.newContext(),pub=await browser.newContext();
const rpc=async(route,params)=>{const r=await admin.request.post(BASE+route,{data:{jsonrpc:'2.0',method:'call',params}});const b=await r.json();assert(!b.error,route+': '+(b.error?.data?.message||''));return b.result;};
const model=(model,method,args=[],kwargs={})=>rpc('/web/dataset/call_kw/'+model+'/'+method,{model,method,args,kwargs});
const bpi=(route,params)=>rpc('/bader_product_intelligence/'+route,params);
const high=fixture.variants[0].id,starter=fixture.variants[1].id;
const data=async()=>bpi('data',{product_tmpl_id:fixture.id,product_variant_id:high});
const save=async(changes={},inherit=[])=>{const s=(await data()).variantContent;return bpi('variant_content/save',{product_tmpl_id:fixture.id,product_variant_id:high,base_revision:s.baseRevision,revision:s.revision,context_revision:s.contextRevision,changes,inherit});};
try{
 assert((await rpc('/web/session/authenticate',{db:DB,...creds})).uid);
 const original=(await data()).variantContent;
 const docs=original.values.documents;docs.title='Manual exclusivo High';docs.buttons[0]={label:'Manual High',kind:'file',url:'',filename:'manual-high.pdf',upload:pdf()};
 const saved=await save({documents:docs});const url=saved.variantContent.values.documents.buttons[0].fileUrl;
 const file=await pub.request.get(BASE+url);assert.equal(file.status(),200);assert.equal(file.headers()['content-type'],'application/pdf');assert((await file.body()).subarray(0,5).toString()==='%PDF-');
 assert.equal(file.headers()['x-content-type-options'],'nosniff');
 assert.equal((await pub.request.get(BASE+url.replace('variant='+high,'variant='+starter))).status(),404);
 assert.equal((await pub.request.get(BASE+url.replace(/v=\d+/,'v=0'))).status(),404);
 const panels=await model('bpi.product.document.panel','search',[[['product_id','=',fixture.id],['product_variant_id','=',high]]]);
 const direct=await pub.request.get(BASE+'/web/content/bpi.product.document.panel/'+panels[0]+'/file_1');assert.notEqual(direct.status(),200);
 result.checks.push('saved_variant_pdf_public_only_on_owned_current_variant_not_private_generic_route');
 await save({},['documents']);assert.equal((await pub.request.get(BASE+url)).status(),404);
 assert(await model('bpi.product.document.panel','search_count',[[['id','=',panels[0]]]]));
 result.checks.push('return_to_inheritance_revokes_document_but_preserves_private_history');
 assert(!(await bpi('data',{product_tmpl_id:fixture.id,product_variant_id:starter})).variantContent.overridden.includes('documents'));
 result.status='PASS';console.log('VARIANT_DOCUMENTS_PASS');
}catch(e){result.status='FAIL';result.failure=String(e).split(creds.password).join('[REDACTED]');throw e;}finally{fs.writeFileSync(path.join(dir,'documents_browser_results.json'),JSON.stringify(result,null,2));await browser.close();}
})().catch(e=>{console.error(String(e.stack).split(creds.password).join('[REDACTED]'));process.exitCode=1;});
