"""All implemented versions. Tests and benchmarks iterate over this registry,
so a new version only has to be added here."""

import search_v1
import search_v2
import search_v3

VERSIONS = {
    "v1": search_v1.METHODS,
    "v2": search_v2.METHODS,
    "v3": search_v3.METHODS,
}
