set -euo pipefail
# Deliberately NO `git init`: this leaves the scaffold dir as a plain,
# non-git directory so Phase 0 must resolve to whole-repo mode on the cwd
# (case 3, "Not a git repo") rather than attempting any PR/diff scoping.
mkdir -p src
cat > src/ratelimit.py <<'EOF'
"""Token-bucket rate limiter.

Invariant: tokens refill lazily (computed on read, no background timer) at
`rate` per second up to `capacity`, and the bucket never exceeds `capacity`.
A request costing `n` tokens is admitted only if the refilled bucket holds at
least `n`. `_now` is injectable for tests; it must be monotonic — a clock that
goes backwards would credit negative elapsed time and under-fill the bucket.
"""
import time


class TokenBucket:
    def __init__(self, rate, capacity, now=time.monotonic):
        self._rate = rate
        self._capacity = capacity
        self._now = now
        self._tokens = float(capacity)
        self._last = now()

    def _refill(self):
        t = self._now()
        elapsed = t - self._last
        self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
        self._last = t

    def allow(self, n=1):
        self._refill()
        if self._tokens >= n:
            self._tokens -= n
            return True
        return False
EOF
cat > README.md <<'EOF'
# ratelimit
Token-bucket limiter for the API gateway. No external deps, no VCS yet.
EOF
