-- Owner-run integration check. All inserted test rows are rolled back.
begin;
do $$
declare
  first_id uuid;
  retry_id uuid;
  request_id uuid := gen_random_uuid();
  fingerprint text := repeat('0',64);
  blocked boolean := false;
begin
  assert not has_table_privilege('anon','public.blog_comments','SELECT');
  assert not has_table_privilege('anon','public.blog_comments','INSERT');
  assert not has_function_privilege('anon','public.submit_blog_comment(text,text,text,text,uuid,uuid)','EXECUTE');
  assert (select bool_and(relrowsecurity) from pg_class where oid in ('public.blog_comments'::regclass,'public.blog_comment_receipts'::regclass));
  first_id := public.submit_blog_comment('integration-test','Connection test','Test only; transaction will roll back.',fingerprint,request_id);
  assert (select status='pending' and is_author=false from public.blog_comments where id=first_id);
  retry_id := public.submit_blog_comment('integration-test','Connection test','Test only; transaction will roll back.',fingerprint,request_id);
  assert first_id = retry_id;
  begin
    perform public.submit_blog_comment('integration-test','Connection test','An unapproved parent must fail.',fingerprint,gen_random_uuid(),first_id);
  exception when sqlstate '22023' then blocked := sqlerrm = 'invalid_parent'; end;
  assert blocked;
  perform public.submit_blog_comment('integration-test','Connection test','Second submission.',fingerprint,gen_random_uuid());
  perform public.submit_blog_comment('integration-test','Connection test','Third submission.',fingerprint,gen_random_uuid());
  blocked := false;
  begin
    perform public.submit_blog_comment('integration-test','Connection test','Fourth submission must fail.',fingerprint,gen_random_uuid());
  exception when raise_exception then blocked := sqlerrm = 'rate_limit'; end;
  assert blocked;
end;
$$;
rollback;
select 'Database checks passed; test rows rolled back' as result;
