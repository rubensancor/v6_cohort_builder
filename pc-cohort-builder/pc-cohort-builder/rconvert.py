"""pandas <-> R data.frame conversion, without python-ohdsi's ``common``.

``ohdsi.common`` offers ``convert_to_r`` / ``convert_from_r`` but imports the
R package ``FeatureExtraction`` the moment it is loaded. That package is not
needed for cohort generation and pulls in Andromeda and a large native build,
so the two conversions the algorithm needs are done here with rpy2 directly.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


def convert_to_r(item: Any) -> Any:
    """A pandas DataFrame becomes an R data.frame; anything else passes through."""
    if not isinstance(item, pd.DataFrame):
        return item
    import rpy2.robjects as ro  # pylint: disable=import-outside-toplevel
    from rpy2.robjects import pandas2ri  # pylint: disable=import-outside-toplevel
    from rpy2.robjects.conversion import localconverter  # pylint: disable=import-outside-toplevel

    with localconverter(ro.default_converter + pandas2ri.converter):
        return ro.conversion.py2rpy(item)


def convert_from_r(item: Any) -> Any:
    """An R data.frame becomes a pandas DataFrame; anything else passes through."""
    import rpy2.robjects as ro  # pylint: disable=import-outside-toplevel

    if not isinstance(item, ro.vectors.DataFrame):
        return item
    from rpy2.robjects import pandas2ri  # pylint: disable=import-outside-toplevel
    from rpy2.robjects.conversion import localconverter  # pylint: disable=import-outside-toplevel

    with localconverter(ro.default_converter + pandas2ri.converter):
        return ro.conversion.rpy2py(item)
