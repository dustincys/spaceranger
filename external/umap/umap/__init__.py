from .umap_ import UMAP

# Workaround: https://github.com/numba/numba/issues/3341
import numba
numba.config.THREADING_LAYER = 'workqueue'

import pkg_resources

__version__ = "0.3.9.1"
