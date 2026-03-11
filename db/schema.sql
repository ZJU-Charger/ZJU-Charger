-- ZJU Charger SQLite 数据库 Schema
-- 此文件定义了所有表结构和索引

-- 1. stations 表（站点基础信息）
CREATE TABLE IF NOT EXISTS stations (
    hash_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    provider TEXT NOT NULL,
    campus_id INTEGER,
    campus_name TEXT,
    lat REAL,
    lon REAL,
    device_ids TEXT DEFAULT '[]',
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT DEFAULT (datetime('now', 'localtime'))
);

-- stations 表索引
CREATE INDEX IF NOT EXISTS idx_stations_provider ON stations(provider);
CREATE INDEX IF NOT EXISTS idx_stations_campus ON stations(campus_id);

-- 2. latest 表（最新快照）
CREATE TABLE IF NOT EXISTS latest (
    hash_id TEXT PRIMARY KEY,
    snapshot_time TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    free INTEGER NOT NULL DEFAULT 0,
    used INTEGER NOT NULL DEFAULT 0,
    total INTEGER NOT NULL DEFAULT 0,
    error INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (hash_id) REFERENCES stations(hash_id) ON DELETE CASCADE
);

-- latest 表索引
CREATE INDEX IF NOT EXISTS idx_latest_station ON latest(hash_id);

-- 3. usage 表（使用情况历史快照）
CREATE TABLE IF NOT EXISTS usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hash_id TEXT NOT NULL,
    snapshot_time TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    free INTEGER NOT NULL DEFAULT 0,
    used INTEGER NOT NULL DEFAULT 0,
    total INTEGER NOT NULL DEFAULT 0,
    error INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (hash_id) REFERENCES stations(hash_id) ON DELETE CASCADE
);

-- usage 表索引
CREATE INDEX IF NOT EXISTS idx_usage_station_time ON usage(hash_id, snapshot_time DESC);
CREATE INDEX IF NOT EXISTS idx_usage_time ON usage(snapshot_time DESC);
