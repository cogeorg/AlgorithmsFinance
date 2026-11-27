"""Pure helpers for the report-style page: number formatting, units, label placement and
the sentences that are computed from the saved results (nothing is hard-coded)."""
import math

import loaders

METHOD_ORDER = ["linear_v1", "binary_v1", "binary_v2", "hash_v1"]
METHOD_LABEL = {"linear_v1": "linear", "binary_v1": "binary v1", "binary_v2": "binary v2",
                "hash_v1": "hash set"}
HIT_LABEL = {"mixed": "mixed", "all-present": "all present", "all-absent": "all absent"}


def sig3(value):
    """3 significant digits with thousands separators: 133.39 -> '133', 0.1769 -> '0.177'."""
    if value == 0:
        return "0"
    digits = 2 - math.floor(math.log10(abs(value)))
    rounded = round(value, digits)
    return f"{rounded:,.{max(digits, 0)}f}"


def round3(value):
    """Round to 3 significant digits (number stays a number)."""
    if value == 0:
        return 0.0
    return round(value, 2 - math.floor(math.log10(abs(value))))


def pick_unit(max_seconds):
    """ms unless every value is below 1 ms (then µs), or below 1 µs (then ns)."""
    if max_seconds >= 1e-3:
        return "ms", 1e3
    if max_seconds >= 1e-6:
        return "µs", 1e6
    return "ns", 1e9


def log_domain(low, high):
    """Powers of ten around [low, high] for a log axis."""
    lo = 10 ** math.floor(math.log10(low))
    hi = 10 ** math.ceil(math.log10(high))
    return [lo, hi if hi > lo else lo * 10]


def spread_labels(values, gap_decades, low_decades, high_decades):
    """Move end-of-line labels apart (in log10 units) so text does not overlap.

    values: {key: y}; returns {key: adjusted y}. The order of the labels is kept.
    """
    order = sorted(values, key=values.get)
    logs = {k: math.log10(values[k]) for k in order}
    for previous, key in zip(order, order[1:]):
        logs[key] = max(logs[key], logs[previous] + gap_decades)
    if order and logs[order[-1]] > high_decades:
        logs[order[-1]] = high_decades
        for key, following in zip(reversed(order[:-1]), reversed(order[1:])):
            logs[key] = min(logs[key], logs[following] - gap_decades)
    return {k: 10 ** max(v, low_decades) for k, v in logs.items()}


def _median(summary, n, q, hit, method, phase):
    row = summary[(summary["n"] == n) & (summary["q"] == q) & (summary["hit_rate"] == hit)
                  & (summary["method"] == method) & (summary["phase"] == phase)]
    return float(row["median_seconds_per_batch"].iloc[0])


def findings(time_summary, mem_summary, hit="mixed"):
    """Two or three plain sentences computed from the saved results."""
    n_max = int(time_summary["n"].max())
    q_large, q_small = int(time_summary["q"].max()), int(time_summary["q"].min())
    ms = lambda seconds: sig3(seconds * 1e3)  # noqa: E731

    def total(method, q, n=n_max):
        return _median(time_summary, n, q, hit, method, "total")

    prepare_b = _median(time_summary, n_max, q_large, hit, "binary_v2", "prepare")
    query_b = _median(time_summary, n_max, q_large, hit, "binary_v2", "query")
    share = round(100 * prepare_b / (prepare_b + query_b))
    sentences = [
        f"At n = {n_max:,} and q = {q_large} ({HIT_LABEL[hit]} hits) the hash set answers the "
        f"batch, including building the set, in {ms(total('hash_v1', q_large))} ms, binary "
        f"search in {ms(total('binary_v2', q_large))} ms ({share} % of it is sorting) and "
        f"linear search in {ms(total('linear_v1', q_large))} ms."]

    sizes = sorted(int(n) for n in time_summary["n"].unique())
    winners = {n: min(["linear_v1", "binary_v2", "hash_v1"],
                      key=lambda m: total(m, q_small, n)) for n in sizes}
    detail = (f"(n = {n_max:,}: linear {ms(total('linear_v1', q_small))} ms, hash set "
              f"{ms(total('hash_v1', q_small))} ms, binary search "
              f"{ms(total('binary_v2', q_small))} ms)")
    if all(w == "linear_v1" for w in winners.values()):
        sentences.append(f"With q = {q_small} linear search has the lowest total time at every "
                         f"n {detail} because it needs no preparation.")
    else:
        names = ", ".join(f"n = {n:,}: {METHOD_LABEL[w]}" for n, w in winners.items())
        sentences.append(f"With q = {q_small} the lowest total time is {names} {detail}.")

    kb = lambda method: sig3(float(mem_summary[                                  # noqa: E731
        (mem_summary["n"] == n_max) & (mem_summary["q"] == q_large)
        & (mem_summary["hit_rate"] == hit) & (mem_summary["method"] == method)
        & (mem_summary["phase"] == "prepare")]["median_current_bytes"].iloc[0]) / 1e3)
    sentences.append(f"At n = {n_max:,} the sorted copy needs {kb('binary_v2')} kB and the "
                     f"set {kb('hash_v1')} kB.")
    return sentences


def version_sentence(time_summary, q, hit):
    """One sentence with the measured v2 / v1 ratios (query phase and total)."""
    versions = loaders.version_comparison(time_summary)
    here = versions[(versions["q"] == q) & (versions["hit_rate"] == hit)
                    & (versions["phase"] == "query")]["v2_over_v1"]
    query_all = versions[versions["phase"] == "query"]["v2_over_v1"]
    total_all = versions[versions["phase"] == "total"]["v2_over_v1"]
    return (f"For the settings above v2 needs {here.min():.2f} to {here.max():.2f} times the "
            f"query time of v1 ({query_all.min():.2f} to {query_all.max():.2f} over all "
            f"settings), while the total time ratio is {total_all.min():.2f} to "
            f"{total_all.max():.2f} because sorting dominates it.")
