// Plain JavaScript is intentional: deploys in Deno and can be tested with Node.
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const POST_ID = /^[a-zA-Z0-9_-]{1,64}$/;
export function publicFields(row) {
  return { id: row.id, post_id: row.post_id, parent_id: row.parent_id,
    author_name: row.author_name, body: row.body, created_at: row.created_at, is_author: row.is_author === true };
}
function defaultKey(value) { try { return JSON.parse(value || '{}').default || ''; } catch { return ''; } }
export function createHandler(env, fetcher = fetch) {
  const site = env.COMMENTS_SITE_URL || 'https://indiantripper.in';
  const origins = new Set((env.COMMENTS_ORIGINS || 'https://indiantripper.in,https://www.indiantripper.in').split(',').map(s => s.trim()));
  const hostnames = new Set((env.COMMENTS_HOSTNAMES || 'indiantripper.in,www.indiantripper.in').split(',').map(s => s.trim()));
  const dbURL = env.SUPABASE_URL || '';
  const dbKey = defaultKey(env.SUPABASE_SECRET_KEYS) || env.SUPABASE_SERVICE_ROLE_KEY || '';
  const publicKey = defaultKey(env.SUPABASE_PUBLISHABLE_KEYS) || env.COMMENTS_PUBLISHABLE_KEY || '';
  let manifest = null, manifestTime = 0, postDetails = {};
  async function isLive(id) {
    // Read only the builder's current public IDs. A withdrawal applies automatically.
    if (!manifest || Date.now() - manifestTime > 15000) {
      const r = await fetcher(site + '/comments-posts.json', { signal: AbortSignal.timeout(8000), cache: 'no-store' });
      if (!r.ok) throw new Error('manifest_unavailable');
      const data = await r.json();
      if (!Array.isArray(data.posts) || data.posts.some(x => typeof x !== 'string')) throw new Error('invalid_manifest');
      manifest = new Set(data.posts); postDetails = data.details || {}; manifestTime = Date.now();
    }
    return manifest.has(id);
  }
  async function rpc(name, data = {}) {
    const response = await fetcher(dbURL + '/rest/v1/rpc/' + name, { method:'POST',
      headers:{apikey:dbKey,'Content-Type':'application/json'},body:JSON.stringify(data),signal:AbortSignal.timeout(8000) });
    if (!response.ok) throw new Error('queue_unavailable');
    return response.status === 204 ? null : response.json();
  }
  function notificationsReady() {
    return !!(env.RESEND_API_KEY && env.COMMENTS_NOTIFY_TO && env.COMMENTS_NOTIFY_FROM);
  }
  async function deliverNotification() {
    if (!notificationsReady()) return { processed:0, configured:false };
    let row;
    try {
      const rows = await rpc('claim_blog_comment_notification');
      row = rows?.[0];
      if (!row) return { processed:0, configured:true };
      if (!await isLive(row.post_id)) {
        await rpc('finish_blog_comment_notification',{p_id:row.comment_id,p_lease:row.lease_token,p_error:'post_unavailable',p_skip:true});
        return {processed:1,skipped:true};
      }
      let payload = row.payload;
      if (!payload) {
        const detail = postDetails[row.post_id] || {};
        const title = Array.from(String(detail.title || ('Post ' + row.post_id)).replace(/[\r\n]/g,' ')).slice(0,120).join('');
        const path = typeof detail.path === 'string' && detail.path.startsWith('/') && !detail.path.startsWith('//') ? detail.path : '/';
        payload = await rpc('prepare_blog_comment_notification',{p_id:row.comment_id,p_lease:row.lease_token,p_payload:{
          from:env.COMMENTS_NOTIFY_FROM,to:[env.COMMENTS_NOTIFY_TO],subject:'Time Turner: new comment on ' + title,
          text:'A comment is waiting for your approval.\n\nPost: ' + title + '\nFrom: ' + row.author_name +
            '\n\n' + Array.from(row.body).slice(0,1000).join('') + (Array.from(row.body).length>1000?'…':'') +
            '\n\nRead the post: ' + site + path + '\nApprove or reject in Supabase:\nhttps://supabase.com/dashboard/project/uyncwplmenormkebmecn/editor/17654?schema=public' +
            '\n\nComment ID: ' + row.comment_id + '\n\nThe comment is not public until you approve it.' }});
      }
      if (!payload) return {processed:0,lease_expired:true};
      const response = await fetcher('https://api.resend.com/emails',{method:'POST',signal:AbortSignal.timeout(10000),
        headers:{Authorization:'Bearer ' + env.RESEND_API_KEY,'Content-Type':'application/json','Idempotency-Key':'comment-alert/' + row.comment_id},body:JSON.stringify(payload)});
      if (!response.ok) throw new Error('provider_http_' + response.status);
      const accepted = await response.json();
      if (typeof accepted.id !== 'string') throw new Error('provider_unconfirmed');
      await rpc('finish_blog_comment_notification',{p_id:row.comment_id,p_lease:row.lease_token});
      return {processed:1,sent:true};
    } catch(error) {
      const reason = /^provider_http_\d{3}$/.test(error?.message) ? error.message : 'notification_retry';
      if (row) await rpc('finish_blog_comment_notification',{p_id:row.comment_id,p_lease:row.lease_token,p_error:reason}).catch(()=>{});
      // Do not log comment text, recipient, provider response or credentials.
      return {processed:row?1:0,retry:true};
    }
  }
  async function boundedJSON(req) {
    const reader = req.body?.getReader(); if (!reader) throw new Error('bad_json');
    let size = 0, chunks = [];
    while (true) {
      const { done, value } = await reader.read(); if (done) break;
      size += value.byteLength;
      if (size > 20000) { await reader.cancel(); throw new Error('too_large'); }
      chunks.push(value);
    }
    const bytes = new Uint8Array(size); let offset = 0;
    for (const part of chunks) { bytes.set(part, offset); offset += part.length; }
    return JSON.parse(new TextDecoder().decode(bytes));
  }
  return async function handler(req) {
    const origin = req.headers.get('origin');
    const headers = { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store',
      'Vary': 'Origin', 'X-Content-Type-Options': 'nosniff' };
    if (origin && origins.has(origin)) headers['Access-Control-Allow-Origin'] = origin;
    const reply = (status, data, extra = {}) => new Response(JSON.stringify(data), { status, headers: { ...headers, ...extra } });
    if (origin && !origins.has(origin)) return reply(403, { error: 'This origin is not allowed.' });
    if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: { ...headers,
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS', 'Access-Control-Allow-Headers': 'apikey, content-type', 'Access-Control-Max-Age': '600' } });
    if (!['GET','POST'].includes(req.method)) return reply(405, { error: 'Method not allowed.' });
    if (!dbURL || !dbKey || !publicKey) return reply(503, { error: 'Comments are temporarily unavailable.' });
    if (new URL(req.url).searchParams.get('task') === 'notify') {
      const supplied = req.headers.get('x-comments-notify-token') || '', expected = env.COMMENTS_NOTIFY_TOKEN || '';
      if (req.method !== 'POST' || expected.length < 32 || supplied !== expected) return reply(401,{error:'Not authorized.'});
      if (!notificationsReady()) return reply(503,{error:'Notifications are not configured.'});
      return reply(200,await deliverNotification());
    }
    if (req.headers.get('apikey') !== publicKey) return reply(401, { error: 'A publishable key is required.' });
    try {
      if (req.method === 'GET') {
        const url = new URL(req.url), id = url.searchParams.get('post_id') || '';
        const rawOffset = url.searchParams.get('offset') || '0';
        if (!POST_ID.test(id) || !/^\d{1,7}$/.test(rawOffset)) return reply(400, { error: 'Invalid post or page.' });
        if (!await isLive(id)) return reply(404, { error: 'Post not available.' });
        const offset = Number(rawOffset);
        const query = new URLSearchParams({ select: 'id,post_id,parent_id,author_name,body,created_at,is_author',
          post_id: 'eq.' + id, status: 'eq.approved', order: 'created_at.asc,id.asc', offset: String(offset), limit: '51' });
        const r = await fetcher(dbURL + '/rest/v1/blog_comments?' + query, { headers: { apikey: dbKey }, signal: AbortSignal.timeout(8000) });
        if (!r.ok) return reply(503, { error: 'Comments could not load. Please try again.' });
        const rows = await r.json();
        if (!Array.isArray(rows)) throw new Error('invalid_rows');
        return reply(200, { comments: rows.slice(0,50).map(publicFields), has_more: rows.length > 50, next_offset: offset + Math.min(rows.length,50) });
      }
      if (!origin || !origins.has(origin)) return reply(403, { error: 'Please submit from the blog.' });
      if (!env.TURNSTILE_SECRET_KEY) return reply(503, { error: 'Comments are not ready yet. Please try again later.' });
      if (!(req.headers.get('content-type') || '').startsWith('application/json')) return reply(415, { error: 'JSON is required.' });
      let data;
      try { data = await boundedJSON(req); } catch { return reply(400, { error: 'Invalid or oversized comment.' }); }
      const allowed = new Set(['post_id','parent_id','author_name','body','turnstile_token','request_id','website']);
      if (!data || Array.isArray(data) || typeof data !== 'object' || Object.keys(data).some(k => !allowed.has(k))) return reply(400, { error: 'Invalid comment fields.' });
      const id = data.post_id, name = typeof data.author_name === 'string' ? data.author_name.trim() : '',
        body = typeof data.body === 'string' ? data.body.replace(/\r\n?/g,'\n').trim() : '', token = data.turnstile_token;
      if (typeof id !== 'string' || !POST_ID.test(id) || (typeof data.request_id !== 'string' || !UUID.test(data.request_id)) ||
          [...name].length < 2 || [...name].length > 60 || /[\u0000-\u001f\u007f]/.test(name) ||
          [...body].length < 2 || [...body].length > 5000 || /[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/.test(body) ||
          (data.parent_id != null && (typeof data.parent_id !== 'string' || !UUID.test(data.parent_id))) || typeof token !== 'string' || token.length < 1 || token.length > 2048 || data.website) {
        return reply(400, { error: 'Please check your name and comment, then try again.' });
      }
      if (!await isLive(id)) return reply(404, { error: 'Post not available.' });
      const verify = await fetcher('https://challenges.cloudflare.com/turnstile/v0/siteverify', { method: 'POST',
        headers: { 'Content-Type': 'application/json' }, signal: AbortSignal.timeout(8000),
        body: JSON.stringify({ secret: env.TURNSTILE_SECRET_KEY, response: token }) });
      if (!verify.ok) return reply(503, { error: 'Spam check is unavailable. Please try again.' });
      const challenge = await verify.json();
      if (!challenge.success || !hostnames.has(challenge.hostname) || challenge.action !== 'comment' || challenge.cdata !== id) {
        return reply(400, { error: 'Please complete the spam check again.' });
      }
      // Hash the proxy-provided client address with a server-only pepper. Never return or log it.
      // Per-client limits are supplemented by a global quota, so spoofing an address cannot bypass all limits.
      const address = (req.headers.get('x-forwarded-for') || req.headers.get('x-real-ip') || 'unknown').split(',')[0].trim();
      const key = await crypto.subtle.importKey('raw', new TextEncoder().encode('comments-ip:' + dbKey), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
      const digest = await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(address));
      const hash = [...new Uint8Array(digest)].map(b => b.toString(16).padStart(2,'0')).join('');
      const r = await fetcher(dbURL + '/rest/v1/rpc/submit_blog_comment', { method: 'POST', signal: AbortSignal.timeout(8000),
        headers: { apikey: dbKey, 'Content-Type': 'application/json' }, body: JSON.stringify({ p_post_id: id,
          p_author_name: name, p_body: body, p_parent_id: data.parent_id || null, p_client_hash: hash, p_request_id: data.request_id }) });
      if (!r.ok) {
        const error = await r.json().catch(() => ({}));
        if (error.message === 'rate_limit') return reply(429, { error: 'Too many comments. Please wait before trying again.' }, { 'Retry-After': '600' });
        if (error.message === 'invalid_parent' || error.message === 'invalid_request') return reply(400, { error: 'This reply could not be added. Please refresh the discussion.' });
        return reply(503, { error: 'Your comment could not be saved. Your text is still here; please try again.' });
      }
      if (notificationsReady()) {
        const job = deliverNotification();
        if (typeof EdgeRuntime !== 'undefined') EdgeRuntime.waitUntil(job);
        else await job;
      }
      return reply(202, { status: 'pending', message: 'Thank you. Your comment will appear after approval.' });
    } catch {
      // Never echo a backend error, key, request body, or exception to the public client.
      return reply(503, { error: 'Comments are temporarily unavailable. Please try again.' });
    }
  };
}
if (typeof Deno !== 'undefined') Deno.serve(createHandler(Deno.env.toObject()));
