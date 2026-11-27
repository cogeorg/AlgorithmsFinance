class OrderBookContract:
    """Public contract; subclasses implement event processing and inspection."""

    def __init__(self):
        self.last_seq = 0

    def process_event(self, event: dict) -> dict:
        """Validate and atomically process an event; return only its fills."""
        raise NotImplementedError("Step 1: matching engine not implemented")

    def AddLimitOrder(self, event: dict) -> dict:
        return self.process_event(event)

    def CancelOrder(self, event: dict) -> dict:
        return self.process_event(event)

    def FillMarketSell(self, event: dict) -> dict:
        return self.process_event(event)

    def inspect_book(self) -> list[dict]:
        """Return detached records: bids descending, asks ascending, then FIFO."""
        raise NotImplementedError("Step 1: inspection not implemented")
