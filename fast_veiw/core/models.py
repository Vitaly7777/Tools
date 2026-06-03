from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Tuple, Any


class SheetState(Enum):
    NOT_STARTED = auto()
    META_LOADED = auto()
    PREVIEW_LOADING = auto()
    PREVIEW_LOADED = auto()
    FULL_LOADING = auto()
    FULL_LOADED = auto()
    PAUSED = auto()
    ERROR = auto()


@dataclass
class SheetInfo:
    name: str
    max_row: int
    max_col: int
    is_active: bool
    effective_rows: int = 0
    filled_rows: int = 0
    loaded_rows: int = 0
    state: SheetState = SheetState.NOT_STARTED
    data_cache: List[Tuple[Any, ...]] = field(default_factory=list)
    last_stable_row: int = 0
    stable_counter: int = 0
