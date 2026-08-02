set -euo pipefail
git init -q -b main .
printf '.origin.git/\n' > .gitignore
mkdir -p src
cat > src/client.py <<'EOF'
"""HTTP client wrapper for the billing API."""
import urllib.request


def fetch(url, timeout=10.0):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.read()
EOF
git add -A
git -c user.email=eval@example.invalid -c user.name=eval commit -qm "init: billing client"
git clone -q --bare . .origin.git
git remote add origin "$PWD/.origin.git"
git fetch -q origin
git checkout -q -b feature/opaque-retry
cat > src/retry.py <<'EOF'
import random
import time

_M = [0.5, 1.3, 3.7, 9.1]


def r(f, *a, **k):
    j = k.pop("_j", 0.4)
    for i, m in enumerate(_M):
        try:
            return f(*a, **k)
        except Exception:
            if i == len(_M) - 1:
                raise
            time.sleep(m * (1 + random.random() * j) ** (i % 3))
EOF
cat >> src/client.py <<'EOF'


def fetch_with_retry(url, timeout=10.0):
    from .retry import r
    return r(fetch, url, timeout=timeout, _j=0.7)
EOF
git add -A
git -c user.email=eval@example.invalid -c user.name=eval commit -qm "add retry helper"
