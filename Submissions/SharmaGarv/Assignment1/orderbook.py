"""Two sequential price-time matching engines; quantities and prices are integers."""
from collections import OrderedDict
import heapq


class Book:
    """Public methods accept an event dict and return only that event's result.

    process(event) validates and dispatches. AddLimitOrder, CancelOrder and
    FillMarketSell use the same validation. inspect() returns detached snapshots.
    No trade history is retained. Invalid inputs leave all state unchanged.
    """
    def __init__(self, counters=False):
        self.active = {}
        self.last_seq = 0
        self.prices = {'BUY': {}, 'SELL': {}}
        self.best = {'BUY': None, 'SELL': None}
        self.bid_quantity = 0
        self.counters = {} if counters else None

    def count(self, name, n=1):
        if self.counters is not None:
            self.counters[name] = self.counters.get(name, 0) + n

    def validate(self, e):
        if not isinstance(e, dict):
            return 'event must be an object'
        if type(e.get('seq')) is not int or e['seq'] <= self.last_seq:
            return 'seq must be a strictly increasing positive integer'
        if not isinstance(e.get('event_id'), str) or not e['event_id']:
            return 'event_id must be a nonempty string'
        kind = e.get('type')
        if kind not in ('LIMIT', 'MARKET_SELL', 'CANCEL'):
            return 'unknown event type'
        key = 'target_order_id' if kind == 'CANCEL' else 'order_id'
        if not isinstance(e.get(key), str) or not e[key]:
            return key + ' must be a nonempty string'
        if kind == 'CANCEL':
            return None
        if e['order_id'] in self.active:
            return 'duplicate live order_id'
        if type(e.get('qty_units')) is not int or e['qty_units'] <= 0:
            return 'qty_units must be a positive integer'
        if kind == 'LIMIT':
            if e.get('side') not in ('BUY', 'SELL'):
                return 'unknown side'
            if type(e.get('price_ticks')) is not int or e['price_ticks'] <= 0:
                return 'price_ticks must be a positive integer'
        return None

    def process(self, event):
        if isinstance(event, dict) and isinstance(event.get('type'), str):
            method = {'LIMIT': self.AddLimitOrder, 'CANCEL': self.CancelOrder,
                      'MARKET_SELL': self.FillMarketSell}.get(event.get('type'))
            if method:
                return method(event)
        return self._execute(event)

    def _execute(self, event):
        reason = self.validate(event)
        if reason:
            return dict(event_id=event.get('event_id') if isinstance(event, dict) else None,
                        status='rejected', reason=reason)
        e = event
        self.last_seq = e['seq']
        if e['type'] == 'CANCEL':
            o = self.active.get(e['target_order_id'])
            qty = o['qty_units'] if o else 0
            if o:
                self._remove(o)
            return dict(event_id=e['event_id'], target_order_id=e['target_order_id'],
                        status='cancelled' if o else 'not_found', cancelled_qty_units=qty)
        incoming_side = e.get('side', 'SELL') if e['type'] == 'LIMIT' else 'SELL'
        opposite = 'SELL' if incoming_side == 'BUY' else 'BUY'
        qty = e['qty_units']
        fills = []
        while qty and self.best[opposite] is not None:
            price = self.best[opposite]
            if e['type'] == 'LIMIT' and ((incoming_side == 'BUY' and price > e['price_ticks'])
                                        or (incoming_side == 'SELL' and price < e['price_ticks'])):
                break
            maker = self._maker(opposite)
            amount = min(qty, maker['qty_units'])
            qty -= amount
            maker['qty_units'] -= amount
            if opposite == 'BUY':
                self.bid_quantity -= amount
            fills.append(dict(maker_id=maker['order_id'], taker_id=e['order_id'],
                              price_ticks=maker['price_ticks'], qty_units=amount))
            self.count('fills')
            if not maker['qty_units']:
                self._remove(maker)
        if e['type'] == 'LIMIT':
            if qty:
                self._add(dict(order_id=e['order_id'], side=incoming_side,
                               price_ticks=e['price_ticks'], qty_units=qty, arrival_seq=e['seq']))
            status = 'resting' if qty else 'filled'
        else:
            status = 'filled' if qty == 0 else ('partial' if fills else 'unfilled')
        return dict(event_id=e['event_id'], order_id=e['order_id'], status=status,
                    unfilled_qty_units=qty, fills=fills)

    def AddLimitOrder(self, event):
        return self._public(event, 'LIMIT')

    def CancelOrder(self, event):
        return self._public(event, 'CANCEL')

    def FillMarketSell(self, event):
        return self._public(event, 'MARKET_SELL')

    def _public(self, event, kind):
        if not isinstance(event, dict) or event.get('type') != kind:
            return dict(event_id=event.get('event_id') if isinstance(event, dict) else None,
                        status='rejected', reason='wrong event type for method')
        return self._execute(event)

    def inspect(self):
        return [dict(o) for o in sorted(self.active.values(), key=lambda o:
                (o['side'] == 'SELL', -o['price_ticks'] if o['side'] == 'BUY'
                 else o['price_ticks'], o['arrival_seq']))]

    def _register(self, o):
        side, price = o['side'], o['price_ticks']
        self.active[o['order_id']] = o
        self.prices[side][price] = self.prices[side].get(price, 0) + 1
        if side == 'BUY':
            self.bid_quantity += o['qty_units']
        if self.best[side] is None or (price > self.best[side] if side == 'BUY' else price < self.best[side]):
            self.best[side] = price

    def _unregister(self, o):
        side, price = o['side'], o['price_ticks']
        del self.active[o['order_id']]
        if side == 'BUY':
            self.bid_quantity -= o['qty_units']
        self.prices[side][price] -= 1
        if not self.prices[side][price]:
            del self.prices[side][price]
            return True
        return False

    def stats(self):
        return dict(active_orders=len(self.active),
                    price_levels=sum(len(v) for v in self.prices.values()),
                    bid_quantity=self.bid_quantity)


class BaselineBook(Book):
    """Lists preserve arrival order; matching scans individual opposite orders.

    Cached best prices avoid scanning on noncrossing passive insertions.
    Removal uses identity search through a list; no delayed garbage is retained.
    """
    def __init__(self, counters=False):
        super().__init__(counters)
        self.orders = {'BUY': [], 'SELL': []}

    def _add(self, o):
        self.orders[o['side']].append(o)
        self._register(o)

    def _maker(self, side):
        candidate = None
        for order in self.orders[side]:
            self.count('maker_scan_entries')
            if order['price_ticks'] == self.best[side]:
                candidate = order
                break
        return candidate

    def _remove(self, o):
        rows = self.orders[o['side']]
        for i, row in enumerate(rows):
            self.count('remove_scan_entries')
            if row is o:
                del rows[i]
                break
        if self._unregister(o):
            prices = self.prices[o['side']]
            self.count('best_price_scan_entries', len(prices))
            self.best[o['side']] = (max(prices) if o['side'] == 'BUY' else min(prices)) if prices else None


class RevisedBook(Book):
    """Price heaps + FIFO OrderedDict per price + active order lookup.

    Lazy price deletion is compacted at H > 2P+32, bounding heap storage even
    during repeated add/cancel cycles. Empty queues are deleted immediately.
    """
    def __init__(self, counters=False):
        super().__init__(counters)
        self.queues = {'BUY': {}, 'SELL': {}}
        self.heaps = {'BUY': [], 'SELL': []}

    def _add(self, o):
        side, price = o['side'], o['price_ticks']
        if price not in self.queues[side]:
            self.queues[side][price] = OrderedDict()
            heapq.heappush(self.heaps[side], -price if side == 'BUY' else price)
            self.count('heap_pushes')
        self.queues[side][price][o['order_id']] = o
        self._register(o)
        self._clean(side)

    def _maker(self, side):
        self.count('queue_head_lookups')
        return next(iter(self.queues[side][self.best[side]].values()))

    def _remove(self, o):
        side, price = o['side'], o['price_ticks']
        del self.queues[side][price][o['order_id']]
        if self._unregister(o):
            del self.queues[side][price]
        self._clean(side)

    def _clean(self, side):
        heap, queues = self.heaps[side], self.queues[side]
        while heap and (-heap[0] if side == 'BUY' else heap[0]) not in queues:
            heapq.heappop(heap)
            self.count('heap_pops')
        if len(heap) > 2 * len(queues) + 32:
            heap[:] = [-p if side == 'BUY' else p for p in queues]
            heapq.heapify(heap)
            self.count('heap_rebuilds')
        self.best[side] = (-heap[0] if side == 'BUY' else heap[0]) if heap else None
