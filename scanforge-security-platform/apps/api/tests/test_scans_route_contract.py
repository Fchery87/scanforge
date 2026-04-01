from app.api.v1.routes.scans import router


def test_delete_scan_route_exists():
    route = next(
        (
            r
            for r in router.routes
            if getattr(r, "path", "") == "/{scan_id}" and "DELETE" in getattr(r, "methods", set())
        ),
        None,
    )

    assert route is not None, "Scans API must expose a DELETE /{scan_id} route for stale scan cleanup"
