-- Owner-only alert outbox. No email credentials or recipient addresses live in source.
begin;
create table if not exists public.blog_comment_notifications (
  comment_id uuid primary key references public.blog_comments(id) on delete cascade,
  state text not null default 'queued' check (state in ('queued','sending','sent','failed','skipped')),
  attempts integer not null default 0,
  next_attempt_at timestamptz not null default now(),
  first_attempt_at timestamptz,
  locked_until timestamptz,
  lease_token uuid,
  payload jsonb,
  last_error text,
  sent_at timestamptz
);
alter table public.blog_comment_notifications enable row level security;
revoke all on public.blog_comment_notifications from public, anon, authenticated;
grant all on public.blog_comment_notifications to service_role;
create index if not exists blog_comment_notifications_due on public.blog_comment_notifications(next_attempt_at) where state in ('queued','sending');

create or replace function public.queue_blog_comment_notification() returns trigger
language plpgsql security definer set search_path='' as $$
begin
  if new.status='pending' and not new.is_author then
    insert into public.blog_comment_notifications(comment_id) values(new.id) on conflict do nothing;
  end if;
  return new;
end;
$$;
revoke all on function public.queue_blog_comment_notification() from public, anon, authenticated;
drop trigger if exists blog_comment_notification_insert on public.blog_comments;
create trigger blog_comment_notification_insert after insert on public.blog_comments
for each row execute function public.queue_blog_comment_notification();

create or replace function public.claim_blog_comment_notification()
returns table(comment_id uuid, lease_token uuid, payload jsonb, post_id text, author_name text, body text)
language plpgsql security definer set search_path='' as $$
declare candidate uuid; token uuid := gen_random_uuid();
begin
  update public.blog_comment_notifications q set state='skipped', last_error='already_moderated'
    from public.blog_comments c where c.id=q.comment_id and c.status<>'pending' and q.state in ('queued','sending');
  update public.blog_comment_notifications q set state='failed', last_error='retry_window_expired'
    where q.state in ('queued','sending') and (q.attempts>=8 or q.first_attempt_at < now()-interval '23 hours')
      and (q.locked_until is null or q.locked_until < now());
  select q.comment_id into candidate from public.blog_comment_notifications q
    where ((q.state='queued' and q.next_attempt_at<=now()) or (q.state='sending' and q.locked_until<now()))
      and q.attempts<8 and (q.first_attempt_at is null or q.first_attempt_at>=now()-interval '23 hours')
    order by q.next_attempt_at,q.comment_id limit 1 for update skip locked;
  if candidate is null then return; end if;
  update public.blog_comment_notifications q set state='sending',attempts=q.attempts+1,
    first_attempt_at=coalesce(q.first_attempt_at,now()),locked_until=now()+interval '2 minutes',lease_token=token
    where q.comment_id=candidate;
  return query select q.comment_id,q.lease_token,q.payload,c.post_id,c.author_name,c.body
    from public.blog_comment_notifications q join public.blog_comments c on c.id=q.comment_id where q.comment_id=candidate;
end;
$$;

create or replace function public.prepare_blog_comment_notification(p_id uuid,p_lease uuid,p_payload jsonb)
returns jsonb language plpgsql security definer set search_path='' as $$
declare result jsonb;
begin
  update public.blog_comment_notifications q set payload=coalesce(q.payload,p_payload)
    where q.comment_id=p_id and q.lease_token=p_lease and q.state='sending' returning q.payload into result;
  return result;
end;
$$;

create or replace function public.finish_blog_comment_notification(p_id uuid,p_lease uuid,p_error text default null,p_skip boolean default false)
returns void language plpgsql security definer set search_path='' as $$
begin
  update public.blog_comment_notifications q set
    state=case when p_skip then 'skipped' when p_error is null then 'sent' when q.attempts>=8 then 'failed' else 'queued' end,
    sent_at=case when p_error is null and not p_skip then now() else q.sent_at end,
    last_error=left(p_error,80),locked_until=null,
    next_attempt_at=now()+make_interval(mins=>least(60,(5*power(2,greatest(q.attempts-1,0)))::integer))
    where q.comment_id=p_id and q.lease_token=p_lease and q.state='sending';
end;
$$;
revoke all on function public.claim_blog_comment_notification() from public,anon,authenticated;
revoke all on function public.prepare_blog_comment_notification(uuid,uuid,jsonb) from public,anon,authenticated;
revoke all on function public.finish_blog_comment_notification(uuid,uuid,text,boolean) from public,anon,authenticated;
grant execute on function public.claim_blog_comment_notification() to service_role;
grant execute on function public.prepare_blog_comment_notification(uuid,uuid,jsonb) to service_role;
grant execute on function public.finish_blog_comment_notification(uuid,uuid,text,boolean) to service_role;
commit;
