from app.core.handler_registry import HandlerRegistry

def test_handler_registry_register_and_get():
    registry = HandlerRegistry()
    def dummy_handler(req, evt):
        return "ok"
    registry.register("dummy", dummy_handler)
    assert registry.get("dummy") is dummy_handler
    assert registry.get("unknown") is None
