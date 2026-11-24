-- New comments are private until the owner approves them in the Supabase dashboard.
-- Website readers have NO direct table access; the Edge Function exposes approved fields.
begin;
create table if not exists public.blog_comments (
  id uuid primary key default gen_random_uuid(),
  post_id text not null check (post_id ~ '^[a-zA-Z0-9_-]{1,64}$'),
  parent_id uuid,
  author_name text not null check (char_length(btrim(author_name)) between 2 and 60),
  body text not null check (char_length(btrim(body)) between 2 and 5000),
  created_at timestamptz not null default now(),
  status text not null default 'pending' check (status in ('pending','approved','rejected')),
  is_author boolean not null default false,
  unique (id, post_id),
  foreign key (parent_id, post_id) references public.blog_comments(id, post_id)
);
create index if not exists blog_comments_public_post on public.blog_comments(post_id, created_at, id) where status = 'approved';
create index if not exists blog_comments_moderation on public.blog_comments(status, created_at desc);
alter table public.blog_comments enable row level security;
revoke all on public.blog_comments from public, anon, authenticated;
grant all on public.blog_comments to service_role;

-- Short-lived, hashed abuse-control receipts. Never contain raw IP addresses.
create table if not exists public.blog_comment_receipts (
  request_id uuid primary key,
  comment_id uuid not null references public.blog_comments(id) on delete cascade,
  client_hash text not null check (client_hash ~ '^[0-9a-f]{64}$'),
  post_id text not null,
  created_at timestamptz not null default now()
);
create index if not exists blog_comment_receipts_client on public.blog_comment_receipts(client_hash, created_at);
create index if not exists blog_comment_receipts_created on public.blog_comment_receipts(created_at);
alter table public.blog_comment_receipts enable row level security;
revoke all on public.blog_comment_receipts from public, anon, authenticated;
grant all on public.blog_comment_receipts to service_role;

create or replace function public.submit_blog_comment(
  p_post_id text, p_author_name text, p_body text, p_client_hash text,
  p_request_id uuid, p_parent_id uuid default null
) returns uuid language plpgsql security definer set search_path = '' as $$
declare v_id uuid; v_existing public.blog_comments%rowtype;
begin
  -- Serialise this low-volume blog's checks and insert, across concurrent instances.
  perform pg_catalog.pg_advisory_xact_lock(274891603);
  delete from public.blog_comment_receipts where created_at < now() - interval '24 hours';
  select c.* into v_existing from public.blog_comments c
    join public.blog_comment_receipts r on r.comment_id = c.id
    where r.request_id = p_request_id and r.client_hash = p_client_hash;
  if found then
    if v_existing.post_id = p_post_id and v_existing.author_name = btrim(p_author_name)
       and v_existing.body = btrim(p_body) and v_existing.parent_id is not distinct from p_parent_id then
      return v_existing.id;
    end if;
    raise exception 'invalid_request' using errcode = '22023';
  end if;
  if p_parent_id is not null and not exists (
    select 1 from public.blog_comments where id = p_parent_id and post_id = p_post_id and status = 'approved'
  ) then raise exception 'invalid_parent' using errcode = '22023'; end if;
  if (select count(*) from public.blog_comment_receipts where client_hash = p_client_hash and created_at > now() - interval '10 minutes') >= 3
     or (select count(*) from public.blog_comment_receipts where client_hash = p_client_hash) >= 20
     or (select count(*) from public.blog_comment_receipts where created_at > now() - interval '1 minute') >= 30
     or (select count(*) from public.blog_comment_receipts where created_at > now() - interval '1 hour') >= 300
  then raise exception 'rate_limit'; end if;
  insert into public.blog_comments(post_id, parent_id, author_name, body, status, is_author)
    values (p_post_id, p_parent_id, btrim(p_author_name), btrim(p_body), 'pending', false) returning id into v_id;
  insert into public.blog_comment_receipts(request_id, comment_id, client_hash, post_id)
    values (p_request_id, v_id, p_client_hash, p_post_id);
  return v_id;
end;
$$;
revoke all on function public.submit_blog_comment(text,text,text,text,uuid,uuid) from public, anon, authenticated;
grant execute on function public.submit_blog_comment(text,text,text,text,uuid,uuid) to service_role;
commit;
