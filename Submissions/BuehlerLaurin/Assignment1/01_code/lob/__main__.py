"""`python run.py lob`: checks that the package imports and lists its versions."""
from lob import METHODS

print("lob: registered versions:", sorted(METHODS) or "none yet")
