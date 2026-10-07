-- Visual Memory — Supabase migration 0001
-- Enables pgvector, creates all tables, indexes, and Row Level Security.
-- Auth identities live in Supabase's built-in auth.users; profiles extends it.

create extension if not exists "vector";

-- ------------------------------------------------------------------ profiles
create table if not exists public.profiles (
    id uuid primary key references auth.users (id) on delete cascade,
    display_name text,
    created_at timestamptz not null default now()
);

-- ------------------------------------------------------------------ cameras
create table if not exists public.cameras (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users (id) on delete cascade,
    name text not null,
    source_type text not null default 'browser',
    status text not null default 'idle',
    config jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    last_seen_at timestamptz
);
create index if not exists ix_cameras_user on public.cameras (user_id);

-- ---------------------------------------------------------- camera_sessions
create table if not exists public.camera_sessions (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users (id) on delete cascade,
    camera_id uuid not null references public.cameras (id) on delete cascade,
    started_at timestamptz not null default now(),
    ended_at timestamptz,
    status text not null default 'started'
);
create index if not exists ix_camera_sessions_user on public.camera_sessions (user_id);
create index if not exists ix_camera_sessions_camera on public.camera_sessions (camera_id);

-- ------------------------------------------------------------------ memories
create table if not exists public.memories (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users (id) on delete cascade,
    camera_id uuid not null references public.cameras (id) on delete cascade,
    timestamp timestamptz not null default now(),
    scene_type text not null default '',
    scene_summary text not null default '',
    activity text not null default '',
    environment text not null default '',
    confidence double precision not null default 0,
    embedding vector(1024),
    -- True for the initial visual baseline memory of a camera (delta "before" state).
    is_baseline boolean not null default false,
    evidence_id uuid,
    created_at timestamptz not null default now()
);
create index if not exists ix_memories_user on public.memories (user_id);
create index if not exists ix_memories_camera on public.memories (camera_id);
create index if not exists ix_memories_user_time on public.memories (user_id, timestamp desc);
create index if not exists ix_memories_camera_time on public.memories (camera_id, timestamp desc);
-- HNSW index for cosine similarity (safe to create on an empty table).
create index if not exists ix_memories_embedding on public.memories
    using hnsw (embedding vector_cosine_ops);

-- ------------------------------------------------------------ memory_objects
create table if not exists public.memory_objects (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users (id) on delete cascade,
    memory_id uuid not null references public.memories (id) on delete cascade,
    name text not null default '',
    normalized_name text not null default '',
    location text not null default '',
    status text not null default 'visible',
    attributes jsonb not null default '{}'::jsonb
);
create index if not exists ix_memory_objects_user on public.memory_objects (user_id);
create index if not exists ix_memory_objects_memory on public.memory_objects (memory_id);
create index if not exists ix_memory_objects_user_norm on public.memory_objects (user_id, normalized_name);

-- ------------------------------------------------------------- memory_events
create table if not exists public.memory_events (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users (id) on delete cascade,
    memory_id uuid not null references public.memories (id) on delete cascade,
    camera_id uuid not null references public.cameras (id) on delete cascade,
    timestamp timestamptz not null default now(),
    event_type text not null default '',
    object_name text not null default '',
    from_location text not null default '',
    to_location text not null default '',
    description text not null default '',
    confidence double precision not null default 0
);
create index if not exists ix_events_user on public.memory_events (user_id);
create index if not exists ix_events_camera on public.memory_events (camera_id);
create index if not exists ix_events_user_time on public.memory_events (user_id, timestamp desc);
create index if not exists ix_events_user_object_time on public.memory_events (user_id, object_name, timestamp desc);
create index if not exists ix_events_user_type_time on public.memory_events (user_id, event_type, timestamp desc);

-- ------------------------------------------------------------ object_history
create table if not exists public.object_history (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users (id) on delete cascade,
    object_key text not null default '',
    camera_id uuid not null references public.cameras (id) on delete cascade,
    memory_id uuid not null references public.memories (id) on delete cascade,
    timestamp timestamptz not null default now(),
    location text not null default '',
    status text not null default 'visible'
);
create index if not exists ix_object_history_user on public.object_history (user_id);
create index if not exists ix_object_history_user_key on public.object_history (user_id, object_key, timestamp desc);

-- ------------------------------------------------------------------ evidence
create table if not exists public.evidence (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users (id) on delete cascade,
    camera_id uuid not null references public.cameras (id) on delete cascade,
    memory_id uuid not null references public.memories (id) on delete cascade,
    timestamp timestamptz not null default now(),
    storage_path text not null default '',
    mime_type text not null default 'image/jpeg'
);
create index if not exists ix_evidence_user on public.evidence (user_id);
create index if not exists ix_evidence_memory on public.evidence (memory_id);

-- ------------------------------------------------------ chat_conversations
create table if not exists public.chat_conversations (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users (id) on delete cascade,
    title text not null default 'New conversation',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index if not exists ix_chat_conversations_user on public.chat_conversations (user_id);

-- ----------------------------------------------------------- chat_messages
create table if not exists public.chat_messages (
    id uuid primary key default gen_random_uuid(),
    conversation_id uuid not null references public.chat_conversations (id) on delete cascade,
    user_id uuid not null references auth.users (id) on delete cascade,
    role text not null default 'user',
    content text not null default '',
    tool_calls jsonb,
    created_at timestamptz not null default now()
);
create index if not exists ix_chat_messages_user on public.chat_messages (user_id);
create index if not exists ix_chat_messages_conversation on public.chat_messages (conversation_id);

-- ==================================================================== RLS
-- Backend uses the service role (bypasses RLS). These policies protect any
-- direct client access via the anon key: users only see their own rows.
alter table public.profiles          enable row level security;
alter table public.cameras           enable row level security;
alter table public.camera_sessions   enable row level security;
alter table public.memories          enable row level security;
alter table public.memory_objects    enable row level security;
alter table public.memory_events     enable row level security;
alter table public.object_history    enable row level security;
alter table public.evidence          enable row level security;
alter table public.chat_conversations enable row level security;
alter table public.chat_messages     enable row level security;

do $$
declare
    t text;
begin
    foreach t in array array[
        'profiles','cameras','camera_sessions','memories','memory_objects',
        'memory_events','object_history','evidence','chat_conversations','chat_messages'
    ]
    loop
        execute format(
            'drop policy if exists %I on public.%I;',
            'own_rows_' || t, t
        );
        if t = 'profiles' then
            execute format(
                'create policy %I on public.%I for all using (id = auth.uid()) with check (id = auth.uid());',
                'own_rows_' || t, t
            );
        else
            execute format(
                'create policy %I on public.%I for all using (user_id = auth.uid()) with check (user_id = auth.uid());',
                'own_rows_' || t, t
            );
        end if;
    end loop;
end $$;

-- ============================================================ storage bucket
-- Evidence bucket must be private; the backend issues signed URLs.
insert into storage.buckets (id, name, public)
values ('evidence', 'evidence', false)
on conflict (id) do nothing;