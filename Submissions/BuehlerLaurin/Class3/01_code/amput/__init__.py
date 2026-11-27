"""Registry: METHODS = {(name, version): callable}.

Register a stub (raise NotImplementedError) before writing tests, so the red
run fails for the right reason instead of collecting nothing."""
METHODS = {}
