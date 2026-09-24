import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from _lib.text import strip_bloat

assert strip_bloat("data.Read moreWhat is attention?") == "data.", \
    f"P1a: {repr(strip_bloat('data.Read moreWhat is attention?'))}"

assert strip_bloat("not possible.Read more5,0(5) info") == "not possible.", \
    f"P1b: {repr(strip_bloat('not possible.Read more5,0(5) info'))}"

assert strip_bloat("text.Read moreWriting about X") == "text.", \
    f"P1c: {repr(strip_bloat('text.Read moreWriting about X'))}"

assert strip_bloat("foo Read more about X") == "foo", \
    f"P1d: {repr(strip_bloat('foo Read more about X'))}"

assert strip_bloat("· Translate this pageWir vergleichen git rebase und merge") == \
    "Wir vergleichen git rebase und merge", \
    f"P2a: {repr(strip_bloat('· Translate this pageWir vergleichen git rebase und merge'))}"

assert strip_bloat("  · Translate this pageSome foreign text here") == \
    "Some foreign text here", \
    f"P2b: {repr(strip_bloat('  · Translate this pageSome foreign text here'))}"

print("All 6 assertions passed.")
