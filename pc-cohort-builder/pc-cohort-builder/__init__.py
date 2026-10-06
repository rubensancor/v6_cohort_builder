"""pc-cohort-builder package.

Entry points, in the order a client calls them on vantage6 5:

1. ``generate_cohort`` — data-extraction step; runs at each node with database
   access, writes the cohort to ``results.cohort``, leaves a one-row dataframe
   with the count in the session.
2. ``cohort_count`` — federated step; reads that row and returns it, which is
   how the count reaches the client.

``central_function`` and ``generate_cohort_count`` are the pre-v5 entry points.
They remain importable so old task definitions fail with a clear message rather
than an obscure crash.
"""

from .central import central_function
from .extract import generate_cohort
from .federated import cohort_count, generate_cohort_count

__all__ = [
    "generate_cohort",
    "cohort_count",
    "central_function",
    "generate_cohort_count",
]
