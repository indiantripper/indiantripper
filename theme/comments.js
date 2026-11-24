/* Guest comments: approved entries only; submissions wait for owner moderation. */
(function () {
  'use strict';
  var section = document.querySelector('[data-blog-comments]');
  if (!section) return;
  var endpoint = section.dataset.endpoint, apiKey = section.dataset.publishableKey, postId = section.dataset.postId;
  var compose = section.querySelector('.comment-compose'), form = section.querySelector('form');
  var status = section.querySelector('[data-comment-status]'), listBox = section.querySelector('[data-live-comments]');
  var list = section.querySelector('[data-comment-list]'), more = section.querySelector('[data-comments-more]');
  var name = form.elements.author_name, body = form.elements.body, send = form.querySelector('[type=submit]');
  var replyContext = form.querySelector('[data-reply-context]'), cancelReply = form.querySelector('[data-cancel-reply]');
  var parentId = null, token = '', widget = null, widgetLoading = null, loading = false, loaded = false, offset = 0;
  var requestId = '', signature = '', entries = new Map(), seen = new Set();
  var preview = section.dataset.preview === 'true';
  function message(text, state) { status.textContent = text; status.dataset.state = state || ''; }
  function el(tag, className, text) { var n = document.createElement(tag); if (className) n.className = className; if (text != null) n.textContent = text; return n; }
  function request(url, options) {
    var controller = new AbortController(), timer = setTimeout(function () { controller.abort(); }, 12000);
    options = options || {}; options.signal = controller.signal;
    options.headers = Object.assign({ apikey: apiKey }, options.headers || {});
    return fetch(url, options).then(function (r) {
      return r.json().catch(function () { throw new Error('Comments are temporarily unavailable. Please try again.'); }).then(function (data) {
        if (!r.ok) throw new Error(typeof data.error === 'string' ? data.error : 'Comments are temporarily unavailable. Please try again.');
        return data;
      });
    }).finally(function () { clearTimeout(timer); });
  }
  function clearReply() { parentId = null; replyContext.textContent = ''; cancelReply.hidden = true; }
  cancelReply.addEventListener('click', clearReply);
  function renderComment(comment) {
    if (seen.has(comment.id)) return;
    seen.add(comment.id);
    var li = el('li', 'comment' + (comment.is_author ? ' owner-comment' : '')); li.id = 'new-comment-' + comment.id;
    var row = el('div', 'comment-body'), avatar = el('span', 'avatar avatar-initial', Array.from(comment.author_name)[0] || 'A');
    avatar.setAttribute('aria-hidden','true');
    var content = el('div'), meta = el('div', 'comment-meta-line');
    meta.append(el('span','comment-author',comment.author_name));
    if (comment.is_author) meta.append(el('span','comment-owner-label','Author'));
    var date = new Date(comment.created_at), time = el('time','mono');
    if (!isNaN(date.valueOf())) { time.dateTime = date.toISOString(); time.textContent = new Intl.DateTimeFormat('en-IN',{dateStyle:'medium'}).format(date); }
    meta.append(time);
    var text = el('div','comment-text',comment.body); text.style.whiteSpace = 'pre-wrap';
    if (/[ऀ-ॿ]/.test(comment.body)) text.lang = 'hi';
    var reply = el('button','comment-reply','Reply'); reply.type = 'button';
    reply.addEventListener('click',function () {
      parentId = comment.id; replyContext.textContent = 'Replying to ' + comment.author_name; cancelReply.hidden = false;
      compose.open = true; startWidget(); body.focus(); compose.scrollIntoView({behavior:'smooth',block:'center'});
    });
    content.append(meta,text,reply); row.append(avatar,content); li.append(row);
    var parent = comment.parent_id && entries.get(comment.parent_id);
    if (parent) {
      var children = parent.querySelector(':scope > ol.children');
      if (!children) { children = el('ol','children'); parent.append(children); }
      children.append(li);
    } else list.append(li);
    entries.set(comment.id,li);
  }
  function load() {
    if (loading || preview) return;
    loading = true; more.disabled = true;
    request(endpoint + '?post_id=' + encodeURIComponent(postId) + '&offset=' + offset).then(function (data) {
      if (!Array.isArray(data.comments)) throw new Error('Comments could not load. Please try again.');
      data.comments.forEach(renderComment); offset = data.next_offset; more.hidden = !data.has_more;
      if (seen.size) listBox.hidden = false;
      loaded = true;
    }).catch(function () {
      // No empty/error block on an otherwise readable article. Show retry feedback when the form is opened.
      if (compose.open) message('Comments could not load. You can try again in a moment.','error');
    }).finally(function () { loading = false; more.disabled = false; });
  }
  more.addEventListener('click',load);
  function loadTurnstile() {
    if (window.turnstile) return Promise.resolve();
    if (widgetLoading) return widgetLoading;
    widgetLoading = new Promise(function (resolve,reject) {
      var script = document.createElement('script'); script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
      script.async = true; script.onload = resolve; script.onerror = function () { script.remove(); widgetLoading = null; reject(new Error('The spam check could not load. Please reopen the form to retry.')); };
      document.head.append(script);
    });
    return widgetLoading;
  }
  function startWidget() {
    if (preview) { message('Comments can be sent from the live website.'); return; }
    if (widget !== null) return;
    loadTurnstile().then(function () {
      if (widget !== null) return;
      widget = window.turnstile.render(form.querySelector('[data-turnstile]'),{
        sitekey:section.dataset.turnstileSiteKey,action:'comment',cData:postId,theme:'auto',size:'flexible',
        callback:function (value) { token = value; send.disabled = false; },
        'expired-callback':function () { token = ''; send.disabled = true; },
        'error-callback':function () { token = ''; send.disabled = true; message('The spam check could not finish. Reopen this form to retry.','error'); }
      });
    }).catch(function (e) { message(e.message,'error'); });
  }
  compose.addEventListener('toggle',function () {
    if (!compose.open) return;
    if (!loaded) load();
    if (widget !== null && !token) window.turnstile.reset(widget);
    startWidget();
  });
  form.addEventListener('submit',function (event) {
    event.preventDefault();
    if (preview || !token || send.disabled) return;
    if (!form.reportValidity()) return;
    var author = name.value.trim(), comment = body.value.replace(/\r\n?/g,'\n').trim();
    if (Array.from(author).length < 2 || Array.from(author).length > 60 || Array.from(comment).length < 2 || Array.from(comment).length > 5000) {
      message('Use 2–60 characters for your name and 2–5,000 for the comment.','error'); return;
    }
    var current = JSON.stringify([author,comment,parentId]);
    if (!requestId || signature !== current) { requestId = crypto.randomUUID(); signature = current; }
    send.disabled = true; message('Sending…');
    request(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({post_id:postId,
      author_name:author,body:comment,parent_id:parentId,request_id:requestId,turnstile_token:token,website:form.elements.website.value})})
      .then(function (data) {
        if (data.status !== 'pending') throw new Error('Your comment could not be confirmed. Please try again.');
        body.value = ''; clearReply(); requestId = ''; signature = '';
        message('Thank you. Your comment will appear after approval.','success');
      }).catch(function (e) { message(e.name === 'AbortError' ? 'The request timed out. Your text is still here; please try again.' : e.message,'error'); })
      .finally(function () { token = ''; send.disabled = true; if (widget !== null) window.turnstile.reset(widget); });
  });
  if ('IntersectionObserver' in window && !preview) {
    var observer = new IntersectionObserver(function (items) { if (items.some(function (x) { return x.isIntersecting; })) { observer.disconnect(); load(); } },{rootMargin:'400px'});
    observer.observe(section);
  } else if (!preview) load();
})();
