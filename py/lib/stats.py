import html
import math
from typing import List, Optional


def get_median(values: List[float]) -> Optional[float]:
    if not values:
        return None
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    mid = n // 2
    if n % 2 == 1:
        return sorted_vals[mid]
    return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2.0


def get_stddev(values: List[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / (n - 1)
    return math.sqrt(variance)


def get_diff_category(delta_lufs: float, delta_tp: float) -> str:
    d = max(abs(delta_lufs), abs(delta_tp))
    if d < 0.10:
        return "Egal"
    elif d < 0.50:
        return "imperceptible"
    elif d < 1.50:
        return "leger"
    elif d < 3.00:
        return "moyen"
    elif d < 6.00:
        return "\u00e9lev\u00e9"
    else:
        return "\u00e9norme"


def html_escape(s: str) -> str:
    return html.escape(s, quote=True)


def format_num(v: float, digits: int = 2) -> str:
    return f"{v:.{digits}f}"
