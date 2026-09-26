"""Reusable Databricks SQL helper for Arsenal Fan 360.

Modes:
  exec-file  : run every statement in a .sql file (';' terminated)
  query      : run one query and pretty-print a result grid

Examples:
  python scripts/dbsql.py exec-file unity_catalog/governance.sql
  python scripts/dbsql.py query "SELECT * FROM ... LIMIT 5"
"""
from __future__ import annotations
import argparse, os, time
from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config

PROFILE = os.environ.get("DBX_PROFILE", "fe-vm-serverless-stable-1acr1x")
WAREHOUSE = os.environ.get("DBX_WAREHOUSE", "4484f27c707c5a31")
_w = None


def client():
    global _w
    if _w is None:
        _w = WorkspaceClient(config=Config(profile=PROFILE))
    return _w


def run(sql: str):
    w = client()
    r = w.statement_execution.execute_statement(
        warehouse_id=WAREHOUSE, statement=sql, wait_timeout="50s")
    while r.status.state.value in ("PENDING", "RUNNING"):
        time.sleep(2)
        r = w.statement_execution.get_statement(r.statement_id)
    if r.status.state.value != "SUCCEEDED":
        err = r.status.error.message if r.status.error else "unknown"
        raise RuntimeError(f"SQL failed: {err}\n  {sql[:200]}")
    cols = [c.name for c in r.manifest.schema.columns] if r.manifest and r.manifest.schema else []
    data = r.result.data_array if (r.result and r.result.data_array) else []
    return cols, data


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
    if buf and "\n".join(buf).strip():
        out.append("\n".join(buf).strip())
    return out


def grid(cols, data, max_w=42):
    lines = []
    widths = [len(c) for c in cols]
    for row in data:
        for i, v in enumerate(row):
            widths[i] = min(max_w, max(widths[i], len(str(v)) if v is not None else 4))
    def fmt(row):
        return " | ".join(str(v if v is not None else "NULL")[:max_w].ljust(widths[i]) for i, v in enumerate(row))
    lines.append(fmt(cols))
    lines.append("-+-".join("-" * w for w in widths))
    for row in data:
        lines.append(fmt(row))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["exec-file", "query"])
    ap.add_argument("target")
    args = ap.parse_args()
    if args.mode == "exec-file":
        with open(args.target) as f:
            stmts = split_statements(f.read())
        for st in stmts:
            try:
                run(st)
                print(f"[OK] {' '.join(st.split())[:80]}")
            except Exception as e:
                if os.environ.get("DBSQL_CONTINUE") == "1":
                    print(f"[SKIP] {' '.join(st.split())[:70]} -> {str(e).split('] ')[-1][:80]}")
                else:
                    raise
    else:
        cols, data = run(args.target)
        print(grid(cols, data))


if __name__ == "__main__":
    main()
