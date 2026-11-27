"""Every test that takes `book` runs once for Version A and once for Version B."""
import pytest

from lob import VERSIONS


@pytest.fixture(params=sorted(VERSIONS))
def book(request):
    return VERSIONS[request.param]()   # fresh, empty book for every test
