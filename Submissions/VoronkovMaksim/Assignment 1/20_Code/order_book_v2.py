"""Indexed price-time order book with bounded stale price entries."""
import heapq


def valid_identifier(value):
    return type(value) is int or (type(value) is str and bool(value))


class OrderBook:
    def __init__(self):
        self.orders_by_id = {}
        self.bids_by_price, self.asks_by_price = {}, {}
        self.bid_heap, self.ask_heap = [], []
        self.bid_heap_prices, self.ask_heap_prices = set(), set()
        self.last_seq = 0

    def _structures(self, side):
        if side == 'BUY':
            return self.bids_by_price, self.bid_heap, self.bid_heap_prices, -1
        return self.asks_by_price, self.ask_heap, self.ask_heap_prices, 1

    def _validate(self, event):
        if not isinstance(event, dict):
            return 'event must be a dictionary'
        if not all(field in event for field in ('seq', 'event_id', 'type')):
            return 'missing common field'
        if type(event['seq']) is not int or event['seq'] <= self.last_seq:
            return 'sequence must be a strictly increasing positive integer'
        kind = event['type']
        if kind not in ('LIMIT', 'MARKET_SELL', 'CANCEL'):
            return 'unknown event type'
        required = {'LIMIT': ('order_id', 'side', 'price_ticks', 'qty_units'),
                    'MARKET_SELL': ('order_id', 'qty_units'),
                    'CANCEL': ('target_order_id',)}[kind]
        if not all(field in event for field in required):
            return 'missing required field'
        identifier_field = 'target_order_id' if kind == 'CANCEL' else 'order_id'
        for field in ('event_id', identifier_field):
            if not valid_identifier(event[field]):
                return f'{field} must be a nonempty string or integer'
        if kind == 'CANCEL':
            return None
        identifier = event['order_id']
        if identifier in self.orders_by_id:
            return 'duplicate live order identifier'
        if kind == 'LIMIT' and event['side'] not in ('BUY', 'SELL'):
            return 'invalid side'
        for field in (('price_ticks', 'qty_units') if kind == 'LIMIT' else ('qty_units',)):
            if type(event[field]) is not int or event[field] <= 0:
                return f'{field} must be a positive integer'
        return None

    def process_event(self, event):
        reason = self._validate(event)
        if reason:
            result = {'status': 'rejected', 'reason': reason}
            if isinstance(event, dict) and 'event_id' in event:
                result['event_id'] = event['event_id']
            return result
        self.last_seq = event['seq']
        if event['type'] == 'CANCEL':
            return self.CancelOrder(event)
        if event['type'] == 'MARKET_SELL':
            return self.FillMarketSell(event)
        return self.AddLimitOrder(event)

    def _rebuild_if_needed(self, side):
        levels, heap, heap_prices, sign = self._structures(side)
        if len(heap) > 3 * len(levels):
            heap[:] = [sign * price for price in levels]
            heapq.heapify(heap)
            heap_prices.clear()
            heap_prices.update(levels)

    def _best_price(self, side):
        levels, heap, heap_prices, sign = self._structures(side)
        while heap and sign * heap[0] not in levels:
            heap_prices.remove(sign * heapq.heappop(heap))
        return sign * heap[0] if heap else None

    def _remove(self, order):
        side, price, identifier = order['side'], order['price_ticks'], order['order_id']
        levels, _, _, _ = self._structures(side)
        del self.orders_by_id[identifier]
        del levels[price][identifier]
        if not levels[price]:
            del levels[price]
            self._rebuild_if_needed(side)

    def _rest(self, event, remaining):
        side, price = event['side'], event['price_ticks']
        levels, heap, heap_prices, sign = self._structures(side)
        if price not in levels:
            levels[price] = {}
            # Reuse an existing stale price entry instead of inserting a duplicate.
            if price not in heap_prices:
                heapq.heappush(heap, sign * price)
                heap_prices.add(price)
        order = {'order_id': event['order_id'], 'side': side, 'price_ticks': price,
                 'qty_units': remaining, 'arrival_seq': event['seq']}
        levels[price][event['order_id']] = order
        self.orders_by_id[event['order_id']] = order

    def _match(self, event, side, limit=None):
        opposite = 'SELL' if side == 'BUY' else 'BUY'
        levels, _, _, _ = self._structures(opposite)
        remaining, fills = event['qty_units'], []
        while remaining:
            price = self._best_price(opposite)
            if price is None or (limit is not None and
                                 ((side == 'BUY' and price > limit) or
                                  (side == 'SELL' and price < limit))):
                break
            queue = levels[price]
            maker = queue[next(iter(queue))]
            quantity = min(remaining, maker['qty_units'])
            fills.append({'maker_id': maker['order_id'], 'taker_id': event['order_id'],
                          'price_ticks': price, 'qty_units': quantity})
            remaining -= quantity
            maker['qty_units'] -= quantity
            if not maker['qty_units']:
                self._remove(maker)
        return remaining, fills

    def AddLimitOrder(self, event):
        remaining, fills = self._match(event, event['side'], event['price_ticks'])
        if remaining:
            self._rest(event, remaining)
        return {'event_id': event['event_id'], 'order_id': event['order_id'],
                'status': 'resting' if remaining else 'filled',
                'unfilled_qty_units': remaining, 'fills': fills}

    def FillMarketSell(self, event):
        remaining, fills = self._match(event, 'SELL')
        return {'event_id': event['event_id'], 'order_id': event['order_id'],
                'status': 'filled' if not remaining else ('partial' if fills else 'unfilled'),
                'unfilled_qty_units': remaining, 'fills': fills}

    def CancelOrder(self, event):
        order = self.orders_by_id.get(event['target_order_id'])
        quantity = order['qty_units'] if order is not None else 0
        if order is not None:
            self._remove(order)
        return {'event_id': event['event_id'], 'target_order_id': event['target_order_id'],
                'status': 'cancelled' if order is not None else 'not_found',
                'cancelled_qty_units': quantity}

    def inspect_book(self):
        orders = list(self.orders_by_id.values())
        return [order.copy() for order in sorted(
            orders, key=lambda o: (0, -o['price_ticks'], o['arrival_seq'])
            if o['side'] == 'BUY' else (1, o['price_ticks'], o['arrival_seq']))]
