-- Online Discussion Forum schema

CREATE TABLE IF NOT EXISTS forum_user (
    user_id     TEXT PRIMARY KEY,
    username    TEXT NOT NULL UNIQUE,
    email       TEXT NOT NULL UNIQUE,
    joined_date TEXT NOT NULL,
    reputation  INTEGER NOT NULL DEFAULT 0,
    role        TEXT NOT NULL DEFAULT 'member',  -- 'member', 'moderator', 'admin'
    is_active   INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS category (
    category_id        TEXT PRIMARY KEY,
    name               TEXT NOT NULL UNIQUE,
    description        TEXT,
    parent_category_id TEXT REFERENCES category(category_id),
    is_active          INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS tag (
    tag_id      TEXT PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    description TEXT,
    usage_count INTEGER NOT NULL DEFAULT 0,
    is_approved INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS thread (
    thread_id     TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    category_id   TEXT NOT NULL REFERENCES category(category_id),
    author_id     TEXT NOT NULL REFERENCES forum_user(user_id),
    created_date  TEXT NOT NULL,
    last_activity TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'open',  -- 'open', 'closed', 'deleted'
    view_count    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS post (
    post_id       TEXT PRIMARY KEY,
    thread_id     TEXT NOT NULL REFERENCES thread(thread_id),
    author_id     TEXT NOT NULL REFERENCES forum_user(user_id),
    content       TEXT NOT NULL,
    created_date  TEXT NOT NULL,
    edited_date   TEXT,
    is_first_post INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS thread_tag (
    thread_id TEXT NOT NULL REFERENCES thread(thread_id),
    tag_id    TEXT NOT NULL REFERENCES tag(tag_id),
    PRIMARY KEY (thread_id, tag_id)
);

CREATE INDEX IF NOT EXISTS idx_thread_category ON thread(category_id);
CREATE INDEX IF NOT EXISTS idx_post_thread     ON post(thread_id);
