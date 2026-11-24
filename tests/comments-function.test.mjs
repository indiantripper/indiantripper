import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
// The production .ts file deliberately contains dependency-free JavaScript.
// Import its exact bytes so the CI runner does not need a TypeScript loader.
const source = await readFile(new URL('../supabase/functions/blog-comments/index.ts', import.meta.url), 'utf8');
const { createHandler, publicFields } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
const env = {SUPABASE_URL:'https://test.supabase.co',SUPABASE_SECRET_KEYS:JSON.stringify({default:'server-secret'}),
  SUPABASE_PUBLISHABLE_KEYS:JSON.stringify({default:'sb_publishable_test'}),TURNSTILE_SECRET_KEY:'turnstile-secret'};
const uuid='ea9f79da-0b67-400f-a770-9cc0fbe546dd';
const valid={post_id:'4227',author_name:'पाठक',body:'बहुत अच्छा लगा।',parent_id:null,request_id:uuid,turnstile_token:'challenge-token',website:''};
const request=(body=valid,extra={})=>new Request('https://test.supabase.co/functions/v1/blog-comments',{
  method:'POST',headers:{origin:'https://indiantripper.in',apikey:'sb_publishable_test','content-type':'application/json',...extra},body:JSON.stringify(body)});
function mock(options={}) {
  const calls=[];
  const fetcher=async (url,init={})=>{
    calls.push({url:String(url),init});
    if(String(url).endsWith('/comments-posts.json'))return Response.json({posts:['4227','2026112401']});
    if(String(url).includes('siteverify'))return Response.json(options.challenge||{success:true,hostname:'indiantripper.in',action:'comment',cdata:'4227'});
    if(String(url).includes('/rpc/'))return options.rpcError?Response.json({message:options.rpcError},{status:400}):Response.json(uuid);
    return Response.json(options.rows||[]);
  };
  return {calls,fetcher};
}
test('valid guest input uses a server-only insert with no approval or author override',async()=>{
  const m=mock(),handler=createHandler(env,m.fetcher),r=await handler(request());
  assert.equal(r.status,202);assert.equal((await r.json()).status,'pending');
  const rpc=m.calls.find(c=>c.url.includes('/rpc/'));assert.ok(rpc);
  assert.equal(rpc.init.headers.apikey,'server-secret');
  const data=JSON.parse(rpc.init.body);assert.equal(data.p_post_id,'4227');assert.equal(data.p_body,valid.body);
  assert.equal(data.p_author_name,valid.author_name);assert.match(data.p_client_hash,/^[0-9a-f]{64}$/);
  assert.equal(data.status,undefined);assert.equal(data.is_author,undefined);
});
test('guest cannot request approval, author status, or use invalid parent/request types',async()=>{
  for(const body of [{...valid,status:'approved'},{...valid,is_author:true},{...valid,parent_id:[uuid]},{...valid,request_id:[uuid]}]) {
    const m=mock(),r=await createHandler(env,m.fetcher)(request(body));assert.equal(r.status,400);assert.equal(m.calls.length,0);
  }
});
test('withdrawn or unknown post IDs are rejected before captcha and database access',async()=>{
  for(const id of ['165','181','3593','missing']) {
    const m=mock(),r=await createHandler(env,m.fetcher)(request({...valid,post_id:id}));assert.equal(r.status,404);
    assert.equal(m.calls.length,1);assert.ok(m.calls[0].url.endsWith('/comments-posts.json'));
  }
});
test('GET requires a live ID and forces approved filtering and public fields',async()=>{
  const row={id:uuid,post_id:'4227',author_name:'Reader',body:'<script>alert(1)</script>',created_at:'2026-11-24T00:00:00Z',parent_id:null,is_author:false,status:'pending',client_hash:'hidden',request_id:uuid};
  const m=mock({rows:[row]}),r=await createHandler(env,m.fetcher)(new Request('https://test.supabase.co/functions/v1/blog-comments?post_id=4227',{headers:{apikey:'sb_publishable_test'}}));
  assert.equal(r.status,200);const data=await r.json();
  const api=m.calls.find(c=>c.url.includes('/rest/v1/blog_comments?'));const params=new URL(api.url).searchParams;
  assert.equal(params.get('status'),'eq.approved');assert.equal(params.get('post_id'),'eq.4227');
  assert.deepEqual(data.comments[0],publicFields(row));assert.equal(data.comments[0].client_hash,undefined);assert.equal(data.comments[0].status,undefined);
  assert.equal(data.comments[0].body,row.body);
});
test('Turnstile failure, wrong host, wrong action or wrong post binding never inserts',async()=>{
  for(const challenge of [{success:false},{success:true,hostname:'evil.test',action:'comment',cdata:'4227'},
    {success:true,hostname:'indiantripper.in',action:'login',cdata:'4227'},
    {success:true,hostname:'indiantripper.in',action:'comment',cdata:'other'}]) {
    const m=mock({challenge}),r=await createHandler(env,m.fetcher)(request());
    assert.equal(r.status,400);assert.ok(!m.calls.some(c=>c.url.includes('/rpc/')));
  }
});
test('missing captcha secret fails closed and never requests insertion',async()=>{
  const m=mock(),r=await createHandler({...env,TURNSTILE_SECRET_KEY:''},m.fetcher)(request());assert.equal(r.status,503);assert.equal(m.calls.length,0);
});
test('cross-origin requests, missing key and honeypot submissions fail',async()=>{
  for(const [body,headers,expected] of [[valid,{origin:'https://evil.test'},403],[valid,{apikey:''},401],[{...valid,website:'spam.test'},{},400]]) {
    const m=mock(),r=await createHandler(env,m.fetcher)(request(body,headers));assert.equal(r.status,expected);assert.equal(m.calls.length,0);
  }
});
test('invalid input or an oversized request never reaches the backend',async()=>{
  for(const body of [{...valid,author_name:'A'},{...valid,body:'a'.repeat(5001)},{...valid,body:'x'.repeat(22000)}, {...valid,author_name:'A\nB'}]) {
    const m=mock(),r=await createHandler(env,m.fetcher)(request(body));assert.equal(r.status,400);assert.equal(m.calls.length,0);
  }
});
test('database rate limit is preserved across requests and presented as 429',async()=>{
  const m=mock({rpcError:'rate_limit'}),r=await createHandler(env,m.fetcher)(request());
  assert.equal(r.status,429);assert.equal(r.headers.get('Retry-After'),'600');
});
test('invalid parent gives a useful error; internal failures never expose backend details',async()=>{
  const m=mock({rpcError:'invalid_parent'}),r=await createHandler(env,m.fetcher)(request());assert.equal(r.status,400);
  const bad=await createHandler(env,async()=>{throw new Error('secret server-secret postgres password');})(request());
  assert.equal(bad.status,503);assert.ok(!(await bad.text()).includes('server-secret'));
});
test('preflight permits only expected headers and methods without credentials',async()=>{
  const r=await createHandler(env,mock().fetcher)(new Request('https://test.supabase.co/functions/v1/blog-comments',{method:'OPTIONS',headers:{origin:'https://indiantripper.in'}}));
  assert.equal(r.status,204);assert.equal(r.headers.get('Access-Control-Allow-Origin'),'https://indiantripper.in');
  assert.equal(r.headers.get('Access-Control-Allow-Credentials'),null);
});
