"""
Arsenal Fan 360 :: Lakeflow runner
==================================
Executes the Bronze -> Silver -> Gold SQL transformation files against a
Databricks SQL Warehouse and captures row-count / execution evidence.

Usage:
    python lakeflow/run_pipeline.py \
        --profile fe-vm-serverless-stable-1acr1x \
        --warehouse 4484f27c707c5a31 \
        --evidence evidence/pipeline_output.txt
"""
from __future__ import annotations
import argparse, os, sys, datetime
from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config

CAT = "serverless_stable_1acr1x_catalog"
SQL_FILES = ["bronze_pipeline.sql", "silver_pipeline.sql", "gold_pipeline.sql"]


def split_statements(sql: str):
    out, buf = [], []
    for line in sql.splitlines():
        s = line.strip()
        if s.startswith("--") or not s:
            continue
        buf.append(line)
        if s.endswith(";"):
            stmt = "\n".join(buf).rstrip().rstrip(";")
            if stmt.strip():
                out.append(stmt)
            buf = []
    if buf:
        stmt = "\n".join(buf).strip()
        if stmt:
            out.append(stmt)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--warehouse", required=True)
    ap.add_argument("--evidence", default="evidence/pipeline_output.txt")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    w = WorkspaceClient(config=Config(profile=args.profile))
    lines = []

    def log(msg=""):
        print(msg)
        lines.append(msg)

    def run(sql, label=""):
        r = w.statement_execution.execute_statement(
            warehouse_id=args.warehouse, statement=sql, wait_timeout="50s")
        # poll if still running
        import time
        while r.status.state.value in ("PENDING", "RUNNING"):
            time.sleep(2)
            r = w.statement_execution.get_statement(r.statement_id)
        state = r.status.state.value
        if state != "SUCCEEDED":
            err = r.status.error.message if r.status.error else "unknown"
            log(f"  [FAILED] {label}  -> {err[:200]}")
            raise SystemExit(f"Statement failed: {label}: {err}")
        data = r.result.data_array if (r.result and r.result.data_array) else None
        return data

    log("=" * 74)
    log("ARSENAL FAN 360 :: LAKEFLOW PIPELINE EXECUTION")
    log(f"Run time (UTC): {datetime.datetime.utcnow().isoformat()}")
    log(f"Warehouse     : {args.warehouse}")
    log(f"Catalog       : {CAT}")
    log("=" * 74)

    for fname in SQL_FILES:
        layer = fname.split("_")[0].upper()
        path = os.path.join(here, fname)
        with open(path) as f:
            statements = split_statements(f.read())
        log(f"\n----- {layer} : {fname}  ({len(statements)} statements) -----")
        for stmt in statements:
            head = " ".join(stmt.split())[:70]
            run(stmt, head)
            log(f"  [OK] {head}")

    # ---- Row-count evidence -------------------------------------------------
    log("\n" + "=" * 74)
    log("ROW COUNTS BY LAYER")
    log("=" * 74)
    checks = [
        ("bronze", "bronze_supporters"), ("bronze", "bronze_web_events"),
        ("bronze", "bronze_ecommerce_orders"), ("bronze", "bronze_ticket_orders"),
        ("bronze", "bronze_marketing_events"),
        ("silver", "silver_supporters"), ("silver", "silver_web_events"),
        ("silver", "silver_ecommerce_orders"), ("silver", "silver_ticket_orders"),
        ("silver", "silver_marketing_events"),
        ("gold", "gold_supporter_360"), ("gold", "gold_supporter_activity"),
    ]
    for schema, tbl in checks:
        data = run(f"SELECT COUNT(*) FROM {CAT}.af360_{schema}.{tbl}", f"count {tbl}")
        cnt = int(data[0][0])
        log(f"  {schema:<7} {tbl:<28} {cnt:>10,} rows")

    # de-dup proof
    data = run(f"SELECT (SELECT COUNT(*) FROM {CAT}.af360_bronze.bronze_ecommerce_orders), "
               f"(SELECT COUNT(*) FROM {CAT}.af360_silver.silver_ecommerce_orders)", "dedup")
    b, s = int(data[0][0]), int(data[0][1])
    log(f"\n  De-duplication check (ecommerce): bronze={b:,} -> silver={s:,} "
        f"({b - s} duplicate orders removed)")

    os.makedirs(os.path.dirname(args.evidence), exist_ok=True)
    with open(args.evidence, "w") as f:
        f.write("\n".join(lines) + "\n")
    log(f"\nEvidence written to {args.evidence}")


if __name__ == "__main__":
    main()
