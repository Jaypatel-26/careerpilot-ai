"""Basic per-process limits for a single free-tier instance, not a distributed security system."""
from collections import defaultdict, deque
from threading import Lock
from time import monotonic
from fastapi import HTTPException, Request

_lock = Lock()
_attempts: dict[str, deque[float]] = defaultdict(deque)


def limit_auth_attempts(request: Request):
    now = monotonic()
    # Do not trust an arbitrary X-Forwarded-For header; configure a trusted proxy separately.
    client = request.client.host if request.client else 'unknown'
    with _lock:
        # Bound memory for inactive clients.
        for key in list(_attempts):
            if not _attempts[key] or _attempts[key][-1] <= now - 60:
                del _attempts[key]
        if client not in _attempts and len(_attempts) >= 10000:
            raise HTTPException(status_code=429, detail='Too many authentication attempts. Try again later.', headers={'Retry-After': '60'})
        attempts = _attempts[client]
        while attempts and attempts[0] <= now - 60:
            attempts.popleft()
        if len(attempts) >= 10:
            raise HTTPException(status_code=429, detail='Too many authentication attempts. Try again later.', headers={'Retry-After': '60'})
        attempts.append(now)
