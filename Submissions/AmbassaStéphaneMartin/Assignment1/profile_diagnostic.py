"""Small, separate profiling and operation counts; never part of primary results."""
import cProfile,io,json,pstats,sys
from pathlib import Path
from order_book import BaselineOrderBook,RevisedOrderBook
import dispatcher

ROOT=Path(__file__).resolve().parent
OUT=ROOT/"results"/"phase1_final"

def run():
    OUT.mkdir(parents=True,exist_ok=True)
    records=[]
    for count in (1000,2000):
        events=[dict(type="LIMIT",seq=i,event_id=f"e{i}",order_id=f"o{i}",side="BUY",
            price_ticks=6000000-i%1000,qty_units=100000000) for i in range(1,count+1)]
        for base in (BaselineOrderBook,RevisedOrderBook):
            class Counted(base):
                probes=0
                def _find_order(self,order_id):
                    self.probes+=len(self._orders) if base is BaselineOrderBook else 1
                    return super()._find_order(order_id)
            book=Counted()
            profile=cProfile.Profile()
            profile.enable()
            for e in events:book.process_event(e)
            profile.disable()
            # For unique passive submissions every Baseline ID lookup scans all live IDs.
            expected=count*(count-1)//2 if base is BaselineOrderBook else count
            assert book.probes==expected
            stream=io.StringIO()
            pstats.Stats(profile,stream=stream).strip_dirs().sort_stats("cumulative").print_stats(15)
            name=f"profile_{base.__name__}_{count}"
            (OUT/(name+".txt")).write_text(stream.getvalue(),encoding="utf-8")
            records.append(dict(version=base.__name__,events=count,active_final=count,id_lookup_probes=book.probes,
                scope="Baseline counts list identifier comparisons for unique misses; Revised counts dictionary get calls, not internal hash-slot probes. Matching scans are additional. Counter/profile overhead included; not primary timing."))
    book=RevisedOrderBook()
    results=dispatcher.replay_file(ROOT/"data"/"worked_example.jsonl",book)
    last=results[-1]
    assert [f["maker_id"] for f in last["fills"]]==["b1","b2","b3","b4"]
    assert [f["qty_units"] for f in last["fills"]]==[100000000,100000000,300000000,100000000]
    proceeds=sum(f["price_ticks"]*f["qty_units"] for f in last["fills"])
    assert proceeds==359400*10000000000
    state=book.inspect_book()
    assert state==dict(bids=[dict(order_id="b4",side="BUY",price_ticks=5970000,qty_units=400000000,arrival_seq=4)],
        asks=[dict(order_id="a1",side="SELL",price_ticks=6010000,qty_units=200000000,arrival_seq=5)])
    capacity_book=RevisedOrderBook()
    for i in range(1,1001):
        capacity_book.process_event(dict(type="LIMIT",seq=i,event_id=f"capacity-add-{i}",order_id=f"c{i}",
            side="BUY",price_ticks=6000000,qty_units=100000000))
    before=dict(live=len(capacity_book.orders_by_id),id_index_shallow_bytes=sys.getsizeof(capacity_book.orders_by_id))
    for i in range(1,1001):
        capacity_book.process_event(dict(type="CANCEL",seq=1000+i,event_id=f"capacity-cancel-{i}",target_order_id=f"c{i}"))
    after=dict(live=len(capacity_book.orders_by_id),id_index_shallow_bytes=sys.getsizeof(capacity_book.orders_by_id))
    assert capacity_book.inspect_book()==dict(bids=[],asks=[])
    value=dict(operation_counts=records,container_capacity=dict(before=before,after=after,
        scope="Separate small getsizeof diagnostic of the ID dictionary only; excludes referents and is not primary traced-memory evidence."),
        worked_example=dict(status="passed",ordered_makers=["b1","b2","b3","b4"],
        proceeds_usd=359400,remaining_b4_units=400000000,ask_unchanged=True))
    (OUT/"profile_and_example.json").write_text(json.dumps(value,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(value))
if __name__=="__main__":run()

