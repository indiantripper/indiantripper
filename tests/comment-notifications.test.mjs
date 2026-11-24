import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const source=await readFile(new URL('../supabase/functions/blog-comments/index.ts',import.meta.url),'utf8');
const {createHandler}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const env={SUPABASE_URL:'https://test.supabase.co',SUPABASE_SECRET_KEYS:JSON.stringify({default:'server-secret'}),
  SUPABASE_PUBLISHABLE_KEYS:JSON.stringify({default:'sb_publishable_test'}),TURNSTILE_SECRET_KEY:'captcha-secret',
  RESEND_API_KEY:'email-secret',COMMENTS_NOTIFY_TO:'owner@example.com',COMMENTS_NOTIFY_FROM:'Time Turner <onboarding@resend.dev>',COMMENTS_NOTIFY_TOKEN:'w'.repeat(64)};
const row={comment_id:'552c6b1b-cc25-4d87-bda0-f392c4b74d97',lease_token:'ea9f79da-0b67-400f-a770-9cc0fbe546dd',
  post_id:'2026112401',author_name:'पाठक',body:'बहुत अच्छा लगा। <script>not HTML</script>',payload:null};
const worker=(token=env.COMMENTS_NOTIFY_TOKEN,method='POST')=>new Request('https://test.supabase.co/functions/v1/blog-comments?task=notify',{
  method,headers:{'x-comments-notify-token':token,'Content-Type':'application/json'},...(method==='POST'?{body:'{}'}:{})});
function mock(options={}){
  const calls=[];
  const fetcher=async(url,init={})=>{
    calls.push({url:String(url),init});
    if(String(url).endsWith('claim_blog_comment_notification'))return Response.json(options.empty?[]:[{...row,...options.row}]);
    if(String(url).endsWith('/comments-posts.json'))return Response.json({posts:['2026112401'],details:{'2026112401':{title:'कम ऑन भाई!',path:'/read/come-on/'}}});
    if(String(url).endsWith('prepare_blog_comment_notification'))return Response.json(JSON.parse(init.body).p_payload);
    if(String(url).endsWith('finish_blog_comment_notification'))return new Response(null,{status:204});
    if(String(url)==='https://api.resend.com/emails'){
      if(options.throwEmail)throw Error('secret provider body should never leak');
      return Response.json(options.emailStatus?{error:'provider secret'}:{id:'email-id'},{status:options.emailStatus||200});
    }
    if(String(url).includes('siteverify'))return Response.json({success:true,hostname:'indiantripper.in',action:'comment',cdata:'2026112401'});
    if(String(url).endsWith('submit_blog_comment'))return Response.json(row.comment_id);
    throw Error('unexpected fetch '+url);
  };
  return {calls,handler:createHandler({...env,...options.env},fetcher)};
}
test('notification worker requires its private token, never just the public key',async()=>{
  const m=mock();
  for(const req of [worker(''),worker('sb_publishable_test'),worker('wrong'),worker(env.COMMENTS_NOTIFY_TOKEN,'GET')])assert.equal((await m.handler(req)).status,401);
  assert.equal(m.calls.length,0);
});
test('alert goes only to the server-configured owner with plain-text preview and stable idempotency',async()=>{
  const m=mock();const r=await m.handler(worker());assert.equal(r.status,200);assert.equal((await r.json()).sent,true);
  const email=m.calls.find(c=>c.url==='https://api.resend.com/emails');const payload=JSON.parse(email.init.body);
  assert.deepEqual(payload.to,['owner@example.com']);assert.match(payload.subject,/कम ऑन भाई/);assert.match(payload.text,/पाठक/);
  assert.match(payload.text,/Approve or reject in Supabase/);assert.match(payload.text,/\/read\/come-on\//);assert.equal(payload.html,undefined);
  assert.equal(email.init.headers['Idempotency-Key'],'comment-alert/'+row.comment_id);
  assert.equal(m.calls.filter(c=>c.url.endsWith('finish_blog_comment_notification')).length,1);
});
test('a persisted retry payload remains unchanged instead of creating a different email',async()=>{
  const payload={from:'original sender',to:['owner@example.com'],subject:'Original subject',text:'Original text'};
  const m=mock({row:{payload}});await m.handler(worker());
  assert.deepEqual(JSON.parse(m.calls.find(c=>c.url==='https://api.resend.com/emails').init.body),payload);
  assert.equal(m.calls.some(c=>c.url.endsWith('prepare_blog_comment_notification')),false);
});
test('provider errors are recorded for retry without exposing secret responses',async()=>{
  for(const options of [{emailStatus:429},{emailStatus:500},{throwEmail:true}]){
    const m=mock(options);const r=await m.handler(worker());const body=await r.text();assert.match(body,/retry/);assert.doesNotMatch(body,/secret/);
    const end=JSON.parse(m.calls.find(c=>c.url.endsWith('finish_blog_comment_notification')).init.body);
    assert.ok(['provider_http_429','provider_http_500','notification_retry'].includes(end.p_error));
  }
});
test('withdrawn posts are skipped without sending an email',async()=>{
  const m=mock({row:{post_id:'165'}});const r=await m.handler(worker());assert.equal((await r.json()).skipped,true);
  assert.equal(m.calls.some(c=>c.url==='https://api.resend.com/emails'),false);
  assert.equal(JSON.parse(m.calls.find(c=>c.url.endsWith('finish_blog_comment_notification')).init.body).p_skip,true);
});
test('missing email configuration and empty queues do not call the provider',async()=>{
  const a=mock({env:{RESEND_API_KEY:''}});assert.equal((await a.handler(worker())).status,503);assert.equal(a.calls.length,0);
  const b=mock({empty:true});assert.equal((await(await b.handler(worker())).json()).processed,0);assert.equal(b.calls.length,1);
});
test('a saved comment still succeeds when sending the alert fails',async()=>{
  const m=mock({emailStatus:500});
  const req=new Request('https://test.supabase.co/functions/v1/blog-comments',{method:'POST',
    headers:{origin:'https://indiantripper.in',apikey:'sb_publishable_test','Content-Type':'application/json'},
    body:JSON.stringify({post_id:'2026112401',author_name:'Reader',body:'A valid comment',request_id:row.comment_id,turnstile_token:'valid-token',website:''})});
  const r=await m.handler(req);assert.equal(r.status,202);assert.equal((await r.json()).status,'pending');
  assert.ok(m.calls.some(c=>c.url.endsWith('finish_blog_comment_notification')&&JSON.parse(c.init.body).p_error));
});
