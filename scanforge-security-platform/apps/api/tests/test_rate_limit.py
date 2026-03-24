from app.middleware.redis_rate_limit import RateLimitState


def test_rate_limit_state_initialization():
    state = RateLimitState()
    assert state.store == {}


def test_rate_limit_allows_under_limit():
    state = RateLimitState()
    limited, remaining = state.check("1.2.3.4", limit=60)
    assert limited is False
    assert remaining == 59


def test_rate_limit_blocks_over_limit():
    state = RateLimitState()
    for _ in range(60):
        state.check("1.2.3.4", limit=60)
    limited, remaining = state.check("1.2.3.4", limit=60)
    assert limited is True
    assert remaining >= 0


def test_rate_limit_different_ips():
    state = RateLimitState()
    for _ in range(60):
        state.check("1.2.3.4", limit=60)
    # Different IP should not be limited
    limited, remaining = state.check("5.6.7.8", limit=60)
    assert limited is False
    assert remaining == 59
