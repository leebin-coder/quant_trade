-- ClickHouse schema for realtime tick data
CREATE DATABASE IF NOT EXISTS quant_trade;

CREATE TABLE IF NOT EXISTS quant_trade.market_realtime_ticks
(
    ts_code String,
    name LowCardinality(String),
    trade Nullable(Float64),
    price Nullable(Float64),
    open Nullable(Float64),
    high Nullable(Float64),
    low Nullable(Float64),
    pre_close Nullable(Float64),
    bid Nullable(Float64),
    ask Nullable(Float64),
    volume Nullable(Float64),
    amount Nullable(Float64),
    b1_v Nullable(Float64),
    b1_p Nullable(Float64),
    b2_v Nullable(Float64),
    b2_p Nullable(Float64),
    b3_v Nullable(Float64),
    b3_p Nullable(Float64),
    b4_v Nullable(Float64),
    b4_p Nullable(Float64),
    b5_v Nullable(Float64),
    b5_p Nullable(Float64),
    a1_v Nullable(Float64),
    a1_p Nullable(Float64),
    a2_v Nullable(Float64),
    a2_p Nullable(Float64),
    a3_v Nullable(Float64),
    a3_p Nullable(Float64),
    a4_v Nullable(Float64),
    a4_p Nullable(Float64),
    a5_v Nullable(Float64),
    a5_p Nullable(Float64),
    date Date,
    time DateTime64(3, 'Asia/Shanghai'),
    source LowCardinality(String),
    raw_json String,
    inserted_at DateTime64(3, 'UTC') DEFAULT now64(3, 'UTC'),
    ver UInt64 DEFAULT toUInt64(toUnixTimestamp64Milli(inserted_at)),
    INDEX idx_time (time) TYPE minmax GRANULARITY 64
)
ENGINE = ReplacingMergeTree(ver)
PARTITION BY toYYYYMMDD(date)
ORDER BY (ts_code, date, time)
SETTINGS index_granularity = 8192;
