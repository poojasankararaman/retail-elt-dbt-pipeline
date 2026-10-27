"""Load raw CSVs into the `raw` schema of the warehouse (bronze layer).

Targets
  duckdb (default) : local file retail.duckdb, zero setup
  snowflake        : set SNOWFLAKE_ACCOUNT / USER / PASSWORD / WAREHOUSE / DATABASE / ROLE

Every row gets lineage columns: _loaded_at and _batch_id. dbt uses _loaded_at for
deduplication, incremental logic and source freshness.

Modes
  replace : drop and recreate each raw table (day 1)
  append  : add rows to existing raw tables (day 2+, simulates a new batch)
"""

from __future__ import annotations

import argparse
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

TABLES = ["customers", "products", "orders", "order_items", "payments"]
CSV_FILES = {t: f"{t}.csv" for t in TABLES}


def read_with_lineage(path: Path, batch_id: str, loaded_at: datetime) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["_loaded_at"] = loaded_at
    df["_batch_id"] = batch_id
    return df


def load_duckdb(frames: dict[str, pd.DataFrame], mode: str, db_path: str) -> None:
    import duckdb

    con = duckdb.connect(db_path)
    con.execute("create schema if not exists raw")
    for table, df in frames.items():
        con.register("_df", df)
        exists = con.execute(
            "select count(*) from information_schema.tables "
            "where table_schema = 'raw' and table_name = ?",
            [table],
        ).fetchall()[0][0]
        if mode == "replace" or not exists:
            con.execute(f"create or replace table raw.{table} as select * from _df")
        else:
            con.execute(f"insert into raw.{table} select * from _df")
        con.unregister("_df")
        n = con.execute(f"select count(*) from raw.{table}").fetchall()[0][0]
        print(f"raw.{table}: +{len(df)} rows (total {n})")
    con.close()


def load_snowflake(frames: dict[str, pd.DataFrame], mode: str) -> None:
    import snowflake.connector
    from snowflake.connector.pandas_tools import write_pandas

    con = snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=os.environ["SNOWFLAKE_DATABASE"],
        role=os.environ.get("SNOWFLAKE_ROLE"),
    )
    cur = con.cursor()
    cur.execute("create schema if not exists RAW")
    for table, df in frames.items():
        df = df.copy()
        df.columns = [c.upper() for c in df.columns]
        write_pandas(
            con,
            df,
            table.upper(),
            schema="RAW",
            auto_create_table=True,
            overwrite=(mode == "replace"),
        )
        print(f"RAW.{table.upper()}: +{len(df)} rows")
    con.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--src", type=Path, default=Path("data/raw"))
    ap.add_argument("--mode", choices=["replace", "append"], default="replace")
    ap.add_argument("--target", choices=["duckdb", "snowflake"], default="duckdb")
    ap.add_argument("--db-path", default="retail.duckdb")
    args = ap.parse_args()

    batch_id = uuid.uuid4().hex[:8]
    loaded_at = datetime.now(UTC).replace(tzinfo=None)
    frames = {}
    for table, fname in CSV_FILES.items():
        path = args.src / fname
        if not path.exists():
            raise SystemExit(f"Missing {path}. Run `make data` first.")
        frames[table] = read_with_lineage(path, batch_id, loaded_at)

    print(f"batch {batch_id} at {loaded_at.isoformat(timespec='seconds')} ({args.mode}, {args.target})")
    if args.target == "duckdb":
        load_duckdb(frames, args.mode, args.db_path)
    else:
        load_snowflake(frames, args.mode)


if __name__ == "__main__":
    main()
