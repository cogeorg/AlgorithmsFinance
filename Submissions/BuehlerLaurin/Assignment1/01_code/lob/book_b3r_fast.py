"""Optional constant-factor B3r variant; acceptance rule is in SPEC.md."""
from lob.book_b3r import OrderBookB3r
from lob.validation import validate, rejection, DUPLICATE_LIVE_ORDER_ID


def validate_fast(event, last_seq, is_live, expected_type=None):
    """Recognize ordinary valid events; delegate every other case to the rules.

    Exact builtin types are an optimization condition, not a narrower domain:
    int/str/dict subclasses and bool take the original validator. No early
    rejection is invented, so its first-failing check order stays authoritative.
    """
    if (type(event) is dict and type(last_seq) is int and
            (expected_type is None or type(expected_type) is str)):
        common_oid = None
        try:
            seq = event['seq']
            if type(seq) is int and seq > 0 and seq > last_seq:
                kind = event['type']
                if type(kind) is str and (expected_type is None or kind == expected_type):
                    eid = event['event_id']
                    if type(eid) is str and eid:
                        if kind == 'LIMIT':
                            oid, side = event['order_id'], event['side']
                            price, qty = event['price_ticks'], event['qty_units']
                            if (type(oid) is str and oid and type(side) is str and side in ('BUY', 'SELL')
                                    and type(price) is int and price > 0 and type(qty) is int and qty > 0):
                                common_oid = oid
                        elif kind == 'MARKET_SELL':
                            oid, qty = event['order_id'], event['qty_units']
                            if type(oid) is str and oid and type(qty) is int and qty > 0:
                                common_oid = oid
                        elif kind == 'CANCEL':
                            target = event['target_order_id']
                            if type(target) is str and target:
                                return None
        except KeyError:
            pass
        # Callback failures are not missing fields and must propagate once.
        if common_oid is not None:
            return DUPLICATE_LIVE_ORDER_ID if is_live(common_oid) else None
    return validate(event, last_seq, is_live, expected_type)


class OrderBookB3rFast(OrderBookB3r):
    def process(self, event):
        # Inline the reference _process body on the timed dispatch path. Direct
        # AddLimitOrder/CancelOrder/FillMarketSell retain the inherited methods,
        # original validator, signatures and expected_type behavior.
        reason = validate_fast(event, self.last_seq, self.orders.__contains__)
        if reason is not None:
            return rejection(event, reason)
        self.last_seq = event['seq']
        result = self._cancel(event) if event['type'] == 'CANCEL' else self._submit(event)
        c = self.counters
        if c is not None:
            c.accepted_events += 1
            if event['type'] == 'LIMIT':
                c.limit_events += 1
            elif event['type'] == 'MARKET_SELL':
                c.market_sell_events += 1
            else:
                c.cancel_events += 1
            c.unfilled_qty_units += result.get('unfilled_qty_units', 0)
            c.active_order_peak = max(c.active_order_peak, len(self.orders))
            c.price_level_peak = max(c.price_level_peak, len(self.bids.levels) + len(self.asks.levels))
        return result

    def _match(self, event, incoming_side, limit):
        # Same B3 matching loop, operations and ordering; bind stable lookups.
        side = self.asks if incoming_side == 'BUY' else self.bids
        remaining, fills = event['qty_units'], []
        c = self.counters
        best_price, remove_level, compact = self._best_price, self._remove_level, self._compact
        orders, append_fill = self.orders, fills.append
        while remaining > 0:
            price = best_price(side, count=True)
            if price is None:
                break
            level = side.levels[price]
            if c is not None:
                c.levels_visited += 1
            if limit is not None:
                if (incoming_side == 'BUY' and price > limit) or (incoming_side == 'SELL' and price < limit):
                    break
            queue = level.queue
            pop_head = queue.popleft
            while remaining > 0 and level.live > 0:
                while not queue[0].alive:
                    pop_head()
                    level.stale -= 1
                    if c is not None:
                        c.stale_skipped += 1
                maker = queue[0]
                qty = min(remaining, maker.qty_units)
                append_fill({'maker_id': maker.order_id, 'taker_id': event['order_id'],
                             'price_ticks': price, 'qty_units': qty})
                if c is not None:
                    c.makers_touched += 1
                    c.fills += 1
                remaining -= qty
                maker.qty_units -= qty
                if maker.qty_units == 0:
                    maker.alive = False
                    pop_head()
                    del orders[maker.order_id]
                    level.live -= 1
            if level.live == 0:
                remove_level(side, price, level, best=True)
            else:
                compact(level)
        return fills, remaining
