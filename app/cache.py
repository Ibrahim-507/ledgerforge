"""Tiny time-based cache for one expensive report.
Use:  from app.cache import ttl_cache
      @ttl_cache(60)
      def balance_sheet_data(...): ...
Do not cache anything that must be live to the second (ledger writes)."""
import time, functools


def ttl_cache(seconds):
    def deco(fn):
        store = {}

        @functools.wraps(fn)
        def wrapper(*a, **k):
            key = (a, tuple(sorted(k.items())))
            hit = store.get(key)
            if hit and time.time() - hit[0] < seconds:
                return hit[1]
            val = fn(*a, **k)
            store[key] = (time.time(), val)
            return val
        wrapper.clear = store.clear
        return wrapper
    return deco
