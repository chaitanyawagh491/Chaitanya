DROP TABLE IF EXISTS users;
CREATE TABLE users (
    username         TEXT PRIMARY KEY,
    password_hash    TEXT NOT NULL,
    role             TEXT NOT NULL DEFAULT 'user',
    hwid             TEXT DEFAULT NULL,
    is_banned        INTEGER DEFAULT 0,
    credits          INTEGER DEFAULT 15,
    credits_unlimited INTEGER DEFAULT 0,
    lifetime_requests INTEGER DEFAULT 0,
    last_request_at  TEXT DEFAULT NULL,
    created_at       TEXT DEFAULT CURRENT_TIMESTAMP,
    last_login       TEXT
);

DROP TABLE IF EXISTS login_history;
CREATE TABLE login_history (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    username         TEXT,
    ip_address       TEXT,
    hwid             TEXT,
    status           TEXT,
    timestamp        TEXT DEFAULT CURRENT_TIMESTAMP
);

DROP TABLE IF EXISTS audit_log;
CREATE TABLE audit_log (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    actor            TEXT NOT NULL,
    action           TEXT NOT NULL,
    target           TEXT,
    ip_address       TEXT,
    details          TEXT,
    timestamp        TEXT DEFAULT CURRENT_TIMESTAMP
);

DROP TABLE IF EXISTS system_config;
CREATE TABLE system_config (
    key              TEXT PRIMARY KEY,
    value            TEXT
);

DROP TABLE IF EXISTS invite_keys;
CREATE TABLE invite_keys (
    key              TEXT PRIMARY KEY,
    is_used          INTEGER DEFAULT 0,
    used_by          TEXT DEFAULT NULL,
    created_at       TEXT DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO system_config (key, value) VALUES ('latest_version', '3.0.0');
INSERT INTO system_config (key, value) VALUES ('download_url', '');
INSERT INTO system_config (key, value) VALUES ('changelog', 'System Release Notes');
INSERT INTO system_config (key, value) VALUES ('announcements', 'System Announcements');
