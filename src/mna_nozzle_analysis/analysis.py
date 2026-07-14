from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from .animation import write_ez_animation
from .carbon import (
    CARBON12_MASS_KG,
    CARBON6_CHARGE_PC,
    carbon_terminal_metric,
    read_particle_extrema_series,
)
from .csvio import write_rows
from .fields import (
    FieldFrame,
    frame