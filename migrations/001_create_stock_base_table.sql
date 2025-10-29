-- 量化交易系统 - 股票基本信息表
-- 文件名: 001_create_stock_base_table.sql
-- 描述: 创建股票基本信息表 t_stock_base

BEGIN;

-- 创建枚举类型
CREATE TYPE exchange_type AS ENUM ('SH', 'SZ', 'BJ', 'HK', 'US');
COMMENT ON TYPE exchange_type IS '交易所类型: SH-上交所, SZ-深交所, BJ-北交所, HK-港交所, US-美交所';

CREATE TYPE stock_status_type AS ENUM ('listed', 'delisted', 'suspended');
COMMENT ON TYPE stock_status_type IS '股票状态: listed-上市, delisted-退市, suspended-停牌';

-- 创建股票基本信息表
CREATE TABLE t_stock_base (
    id SERIAL PRIMARY KEY,
    exchange exchange_type NOT NULL,
    stock_code VARCHAR(20) NOT NULL,
    stock_name VARCHAR(100) NOT NULL,
    company_name VARCHAR(200) NOT NULL,
    listing_date DATE NOT NULL,
    industry VARCHAR(100),
    status stock_status_type DEFAULT 'listed',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 添加表注释
COMMENT ON TABLE t_stock_base IS '股票基本信息表';

-- 添加字段注释
COMMENT ON COLUMN t_stock_base.id IS '主键ID';
COMMENT ON COLUMN t_stock_base.exchange IS '交易所';
COMMENT ON COLUMN t_stock_base.stock_code IS '证券代码';
COMMENT ON COLUMN t_stock_base.stock_name IS '证券简称';
COMMENT ON COLUMN t_stock_base.company_name IS '公司全称';
COMMENT ON COLUMN t_stock_base.listing_date IS '上市日期';
COMMENT ON COLUMN t_stock_base.industry IS '所属行业';
COMMENT ON COLUMN t_stock_base.status IS '股票状态';
COMMENT ON COLUMN t_stock_base.created_at IS '创建时间';
COMMENT ON COLUMN t_stock_base.updated_at IS '更新时间';

-- 创建唯一约束
ALTER TABLE t_stock_base ADD CONSTRAINT uq_stock_exchange_code
    UNIQUE (exchange, stock_code);

-- 创建索引
CREATE INDEX idx_stock_base_exchange ON t_stock_base (exchange);
CREATE INDEX idx_stock_base_code ON t_stock_base (stock_code);
CREATE INDEX idx_stock_base_name ON t_stock_base (stock_name);
CREATE INDEX idx_stock_base_company_name ON t_stock_base (company_name);
CREATE INDEX idx_stock_base_listing_date ON t_stock_base (listing_date);
CREATE INDEX idx_stock_base_status ON t_stock_base (status);
CREATE INDEX idx_stock_base_industry ON t_stock_base (industry);
CREATE INDEX idx_stock_base_created_at ON t_stock_base (created_at);

-- 创建更新时间触发器函数
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 创建触发器
CREATE TRIGGER update_t_stock_base_updated_at
    BEFORE UPDATE ON t_stock_base
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

COMMIT;