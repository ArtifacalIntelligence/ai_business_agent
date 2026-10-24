-- ===== Day 1: documents =====
create table if not exists documents (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) not null,
  filename text not null,
  file_type text,
  extracted_text text,
  created_at timestamptz default now()
);

alter table documents enable row level security;

drop policy if exists "own docs" on documents;
create policy "own docs" on documents for all
  using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- ===== Day 2: analyses =====
create table if not exists analyses (
  id uuid primary key default gen_random_uuid(),
  document_id uuid references documents(id) on delete cascade not null,
  user_id uuid references auth.users(id) not null,
  result jsonb not null,
  model text,
  created_at timestamptz default now()
);

alter table analyses enable row level security;

drop policy if exists "own analyses" on analyses;
create policy "own analyses" on analyses for all
  using (auth.uid() = user_id) with check (auth.uid() = user_id);

select table_name from information_schema.tables
where table_schema = 'public' order by table_name;

-- ===== Day 3: actions, tasks, audit =====


create table if not exists proposed_actions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) not null,
  document_id uuid references documents(id) on delete cascade not null,
  analysis_id uuid references analyses(id) on delete cascade,
  action_type text not null check (action_type in ('create_task','schedule_meeting','send_email')),
  payload jsonb not null,
  status text not null default 'pending'
    check (status in ('pending','approved','rejected','executed','failed')),
  result jsonb,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists tasks (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) not null,
  action_id uuid references proposed_actions(id) on delete set null,
  title text not null,
  owner text,
  deadline text,
  status text not null default 'todo' check (status in ('todo','done')),
  created_at timestamptz default now()
);

create table if not exists audit_log (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) not null,
  action_id uuid references proposed_actions(id) on delete set null,
  event text not null,
  details jsonb,
  created_at timestamptz default now()
);

alter table proposed_actions enable row level security;
alter table tasks enable row level security;
alter table audit_log enable row level security;

drop policy if exists "own actions" on proposed_actions;
create policy "own actions" on proposed_actions for all
  using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "own tasks" on tasks;
create policy "own tasks" on tasks for all
  using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- audit log is append-only: users can read and add rows, never edit or delete
drop policy if exists "read own audit" on audit_log;
create policy "read own audit" on audit_log for select using (auth.uid() = user_id);
drop policy if exists "add own audit" on audit_log;
create policy "add own audit" on audit_log for insert with check (auth.uid() = user_id);

-- ===== Day 5: 'executing' status (prevents double execution) =====
do $$
declare c text;
begin
  for c in
    select conname from pg_constraint
    where conrelid = 'public.proposed_actions'::regclass
      and contype = 'c'
      and pg_get_constraintdef(oid) ilike '%status%'
  loop
    execute format('alter table public.proposed_actions drop constraint %I', c);
  end loop;
end $$;

alter table public.proposed_actions
  add constraint proposed_actions_status_check
  check (status in ('pending','approved','rejected','executing','executed','failed'));