-- All test rows and state changes are rolled back; no email is sent.
begin;
do $$
declare id uuid := gen_random_uuid(); first_lease uuid; second_lease uuid; job record; saved jsonb;
begin
  assert not has_table_privilege('anon','public.blog_comment_notifications','SELECT');
  assert not has_table_privilege('anon','public.blog_comment_notifications','INSERT');
  assert not has_function_privilege('anon','public.claim_blog_comment_notification()','EXECUTE');
  assert not has_function_privilege('authenticated','public.prepare_blog_comment_notification(uuid,uuid,jsonb)','EXECUTE');
  insert into public.blog_comments(id,post_id,author_name,body) values(id,'notification-test','Notification test','Rolled-back test.');
  assert (select count(*)=1 from public.blog_comment_notifications q where q.comment_id=id);
  update public.blog_comment_notifications q set next_attempt_at=now()-interval '1 year' where q.comment_id=id;
  select * into job from public.claim_blog_comment_notification();
  assert job.comment_id=id; first_lease:=job.lease_token;
  saved:=public.prepare_blog_comment_notification(id,first_lease,'{"subject":"Original test"}'::jsonb);
  assert saved->>'subject'='Original test';
  saved:=public.prepare_blog_comment_notification(id,first_lease,'{"subject":"Must not replace"}'::jsonb);
  assert saved->>'subject'='Original test';
  perform public.finish_blog_comment_notification(id,first_lease,'provider_http_500');
  assert (select q.state='queued' and q.attempts=1 and q.next_attempt_at>now() from public.blog_comment_notifications q where q.comment_id=id);
  update public.blog_comment_notifications q set next_attempt_at=now()-interval '1 year' where q.comment_id=id;
  select * into job from public.claim_blog_comment_notification();
  assert job.comment_id=id; second_lease:=job.lease_token; assert second_lease<>first_lease;
  perform public.finish_blog_comment_notification(id,first_lease);
  assert (select q.state='sending' from public.blog_comment_notifications q where q.comment_id=id);
  perform public.finish_blog_comment_notification(id,second_lease);
  assert (select q.state='sent' and q.attempts=2 and q.sent_at is not null from public.blog_comment_notifications q where q.comment_id=id);
end;
$$;
rollback;
select 'Notification queue checks passed; test rows rolled back' as result,
  exists(select 1 from pg_available_extensions where name='pg_cron') as cron_available,
  exists(select 1 from pg_available_extensions where name='pg_net') as http_available,
  exists(select 1 from pg_extension where extname='supabase_vault') as vault_enabled;
