"""Data loading interfaces; arithmetic preserved from the frozen core."""
import json
from pathlib import Path
from .domain import Book, _vol_vector
from .simulation import _correlation_root


def load_study(path):
    raw = json.loads(Path(path).read_text())
    values = dict(raw["book"])
    for key in ("names", "spots", "strikes", "notionals", "pricing_vols"):
        values[key] = tuple(values[key])
    book = Book(**values)
    _correlation_root(raw["scenario"]["correlation"], len(book.names))
    _vol_vector(raw["scenario"]["path_vols"], len(book.names), positive=False)
    return book, raw

