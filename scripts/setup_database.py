"""Set up Supabase database tables. Run once."""
import sys
sys.path.insert(0, ".")

from app.database.connection import supabase

SQL_STATEMENTS = [
    """CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        telegram_id BIGINT UNIQUE NOT NULL,
        first_name VARCHAR(100) DEFAULT '',
        language VARCHAR(10) DEFAULT 'gu',
        district VARCHAR(100),
        preferred_crop VARCHAR(100),
        created_at TIMESTAMPTZ DEFAULT NOW(),
        last_active TIMESTAMPTZ DEFAULT NOW()
    )""",
    """CREATE TABLE IF NOT EXISTS disease_queries (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id),
        image_url TEXT,
        crop_type VARCHAR(100),
        disease_result JSONB,
        confidence FLOAT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )""",
    """CREATE TABLE IF NOT EXISTS mandi_prices (
        id SERIAL PRIMARY KEY,
        crop_name VARCHAR(100),
        crop_name_gu VARCHAR(100),
        district VARCHAR(100),
        market_name VARCHAR(100),
        min_price DECIMAL,
        max_price DECIMAL,
        modal_price DECIMAL,
        arrival_qty DECIMAL,
        price_date DATE,
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )""",
    """CREATE TABLE IF NOT EXISTS analytics (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id),
        event_type VARCHAR(50),
        metadata JSONB DEFAULT '{}',
        created_at TIMESTAMPTZ DEFAULT NOW()
    )""",
]


def setup():
    print("Setting up database tables...")
    for sql in SQL_STATEMENTS:
        table_name = sql.split("IF NOT EXISTS ")[1].split(" (")[0]
        try:
            supabase.postgrest.rpc("exec_sql", {"query": sql}).execute()
            print(f"  ✓ {table_name}")
        except Exception as e:
            print(f"  ✗ {table_name}: {e}")
            print(f"    → Run this SQL manually in Supabase SQL Editor")

    print("\nDone! If any tables failed, copy the SQL from this script")
    print("and run it in your Supabase Dashboard → SQL Editor.")


if __name__ == "__main__":
    setup()
