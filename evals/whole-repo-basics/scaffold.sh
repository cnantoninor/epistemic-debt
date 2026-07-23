set -euo pipefail
git init -q -b main .
mkdir -p src
cat > src/ttl_cache.py <<'EOF'
"""In-memory TTL cache with LRU eviction.

Invariant: entries are evicted LRU-first, but an expired entry is always
evicted before any live entry regardless of recency. `_clock` is injectable
for tests; wall-clock drift between processes is NOT handled.
"""
import time


class TTLCache:
    def __init__(self, max_size=128, ttl_seconds=60.0, clock=time.monotonic):
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._clock = clock
        self._data = {}   # key -> (value, expires_at)
        self._order = []  # LRU order, oldest first

    def get(self, key, default=None):
        entry = self._data.get(key)
        if entry is None:
            return default
        value, expires_at = entry
        if self._clock() >= expires_at:
            self._delete(key)
            return default
        self._touch(key)
        return value

    def put(self, key, value):
        if key not in self._data and len(self._data) >= self._max_size:
            self._evict_one()
        self._data[key] = (value, self._clock() + self._ttl)
        self._touch(key)

    def _touch(self, key):
        if key in self._order:
            self._order.remove(key)
        self._order.append(key)

    def _evict_one(self):
        now = self._clock()
        for key in self._order:
            if now >= self._data[key][1]:
                self._delete(key)
                return
        self._delete(self._order[0])

    def _delete(self, key):
        self._data.pop(key, None)
        self._order.remove(key)
EOF
cat > README.md <<'EOF'
# ttl-cache
Tiny in-memory TTL+LRU cache used by the ingestion workers.
EOF
git add -A
git -c user.email=eval@example.invalid -c user.name=eval commit -qm "init: ttl cache"
