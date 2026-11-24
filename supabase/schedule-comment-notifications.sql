-- Run after deploying blog-comments and adding the matching private retry token
-- to Edge Function secrets (COMMENTS_NOTIFY_TOKEN) and Vault (blog_comments_notify_token).
-- This file contains no credentials. The scheduled command decrypts only at runtime.
create extension if not exists pg_cron with schema pg_catalog;
create extension if not exists pg_net with schema extensions;
do $$
begin
  if not exists(select 1 from vault.decrypted_secrets where name='blog_comments_notify_token' and length(decrypted_secret)>=32) then
    raise exception 'Create blog_comments_notify_token in Vault before scheduling alerts';
  end if;
end;
$$;
select cron.schedule('blog-comment-alerts','* * * * *',$job$
  select net.http_post(
    url:='https://uyncwplmenormkebmecn.supabase.co/functions/v1/blog-comments?task=notify',
    headers:=jsonb_build_object('Content-Type','application/json','x-comments-notify-token',
      (select decrypted_secret from vault.decrypted_secrets where name='blog_comments_notify_token')),
    body:='{}'::jsonb,timeout_milliseconds:=30000
  );
$job$);
