# Static routing

**implemented**, đối chiếu **2026-08-16**, cho static và default route với hai
form riêng. QML `UI/qml/features/routing/static/StaticRoutingForm.qml` và
`DefaultRoutingForm.qml`; persistence `static_route.py`, `static_default.py`;
worker/template trong `features/routing/worker.py`. Validate prefix/next-hop/
distance và ownership; save/delete dùng transaction. Test:
`test_database_routing_contract.py`, `test_static_route_sync.py`,
`unit/test_static_default.py` và dev-mode worker.
