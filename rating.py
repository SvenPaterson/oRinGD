# rating.py
from dataclasses import dataclass
from typing import List, Tuple

Crack = Tuple[str, float]  # ("Internal"|"External"|"Split", percent of CSD)

@dataclass(frozen=True)
class Metrics:
    # raw inputs summarized
    num_cracks: int
    total_pct: float
    internal_pct: List[float]
    external_pct: List[float]
    has_split: bool
    # derived counts/flags used by table & rules
    num_lt25: int
    num_lt50: int
    all_ext_lt10: bool
    all_ext_lt25: bool
    all_ext_lt50: bool
    internal_50_80_count: int
    internal_above_80: int
    internal_above_50: int
    has_three_internal_above_50: bool

def compute_metrics(cracks: List[Crack]) -> Metrics:
    if not cracks:
        return Metrics(
            num_cracks=0, total_pct=0.0,
            internal_pct=[], external_pct=[], has_split=False,
            num_lt25=0, num_lt50=0,
            all_ext_lt10=True, all_ext_lt25=True, all_ext_lt50=True,
            internal_50_80_count=0, internal_above_80=0,
            internal_above_50=0, has_three_internal_above_50=False
        )

    internal = [p for (t, p) in cracks if t == "Internal"]
    external = [p for (t, p) in cracks if t == "External"]
    has_split = any(t == "Split" for t, _ in cracks)
    allp = internal + external
    total = sum(allp)

    num_lt25 = sum(1 for p in allp if p < 25)
    num_lt50 = sum(1 for p in allp if p < 50)

    all_ext_lt10 = all(p < 10 for p in external) if external else True
    all_ext_lt25 = all(p < 25 for p in external) if external else True
    all_ext_lt50 = all(p < 50 for p in external) if external else True

    internal_50_80_count = sum(1 for p in internal if 50 <= p <= 80)
    internal_above_80 = sum(1 for p in internal if p > 80)
    internal_above_50 = sum(1 for p in internal if p > 50)
    has_three_internal_above_50 = internal_above_50 >= 3

    return Metrics(
        num_cracks=len(cracks),
        total_pct=total,
        internal_pct=internal,
        external_pct=external,
        has_split=has_split,
        num_lt25=num_lt25,
        num_lt50=num_lt50,
        all_ext_lt10=all_ext_lt10,
        all_ext_lt25=all_ext_lt25,
        all_ext_lt50=all_ext_lt50,
        internal_50_80_count=internal_50_80_count,
        internal_above_80=internal_above_80,
        internal_above_50=internal_above_50,
        has_three_internal_above_50=has_three_internal_above_50
    )

def assign_rating_from_metrics(m: Metrics) -> int:
    if m.num_cracks == 0:
        return 0
    if m.has_split:
        return 5

    # Rating 1
    if m.total_pct <= 100 and m.num_lt25 == m.num_cracks and m.all_ext_lt10:
        return 1

    # Rating 4 triggers
    if (m.total_pct > 300
        or m.internal_above_80 >= 1
        or m.has_three_internal_above_50
        or not m.all_ext_lt50):
        return 4

    # Rating 2
    if m.total_pct <= 200 and m.num_lt50 == m.num_cracks and m.all_ext_lt25:
        return 2

    # Rating 3
    if m.total_pct <= 300 and m.internal_50_80_count <= 2 and m.all_ext_lt50:
        return 3

    return 4

def assign_iso23936_rating(cracks: List[Crack]) -> int:
    return assign_rating_from_metrics(compute_metrics(cracks))

def table_values(m: Metrics) -> List[str]:
    """
    Values for your Value-column rows, in your current row order:
      0: Total crack length (% of CSD)
      1: # cracks that are <25% CSD
      2: All ext. cracks <10% CSD
      3: # cracks that are <50% CSD
      4: All ext. cracks <25% CSD
      5: Are there 2 or fewer int. cracks 50–80% CSD (we show the count)
      6: All ext. cracks <50% CSD
      7: One or more int. crack >80% CSD
      8: Three or more int. cracks >50% CSD
      9: Any splits present
    """
    return [
        f"{m.total_pct:.2f}%",
        str(m.num_lt25),
        "Yes" if m.all_ext_lt10 else "No",
        str(m.num_lt50),
        "Yes" if m.all_ext_lt25 else "No",
        str(m.internal_50_80_count),
        "Yes" if m.all_ext_lt50 else "No",
        "Yes" if m.internal_above_80 >= 1 else "No",
        "Yes" if m.has_three_internal_above_50 else "No",
        "Yes" if m.has_split else "No",
    ]
