set -euo pipefail
git init -q -b main .
mkdir -p src
cat > src/pipeline.py <<'EOF'
"""Batch ETL pipeline: reads events, dedupes by (user_id, day), writes parquet."""


def dedupe(events):
    seen = set()
    out = []
    for e in events:
        key = (e["user_id"], e["ts"][:10])
        if key not in seen:
            seen.add(key)
            out.append(e)
    return out
EOF
git add -A
git -c user.email=eval@example.invalid -c user.name=eval commit -qm "init: etl pipeline"
