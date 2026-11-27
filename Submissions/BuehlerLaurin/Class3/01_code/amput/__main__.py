"""`python run.py amput`: checks that the package imports and lists its versions."""
from amput import METHODS

print("amput: registered versions:", sorted(METHODS) or "none yet")
