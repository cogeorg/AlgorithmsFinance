"""Create repeatable integer IDs and membership queries for Lab 1."""

import random


def generate_data(n, q, hit_rate=0.5, allow_duplicates=True, seed=42):
    """Return unsorted IDs and shuffled queries with the requested hit rate.

    The number of hits is rounded to the nearest whole query, with .5 rounded
    upward. Misses are above every generated ID, so they cannot occur by
    accident. The local random generator does not change global RNG state.
    """
    if type(n) is not int or type(q) is not int or type(seed) is not int:
        raise TypeError("n, q, and seed must be integers, not Booleans")
    if type(allow_duplicates) is not bool:
        raise TypeError("allow_duplicates must be a Boolean")
    if type(hit_rate) not in (int, float) or not 0 <= hit_rate <= 1:
        raise ValueError("hit_rate must be a number between 0 and 1")
    if n < 0 or q < 0:
        raise ValueError("n and q must be nonnegative")
    if n == 0 and q > 0 and hit_rate > 0:
        raise ValueError("positive hit rate is impossible with no IDs")

    rng = random.Random(seed)
    if allow_duplicates:
        limit = max(2, n // 2)
        ids = [rng.randrange(-limit, limit) for _ in range(n)]
    else:
        ids = rng.sample(range(-2 * n, 2 * n + 1), n)

    hit_count = int(q * hit_rate + 0.5)
    queries = [rng.choice(ids) for _ in range(hit_count)]
    first_miss = max(ids, default=0) + 1
    queries.extend(first_miss + i for i in range(q - hit_count))
    rng.shuffle(queries)
    return ids, queries
