from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ParseConfig:
    engine: str = 'pdfplumber-lines'
    pages: tuple[int, ...] | None = None
    engine_settings: dict[str, Any] = field(default_factory=dict)
    engines: tuple[str, ...] = ('pdfplumber-lines', 'pdfplumber-text', 'camelot-stream', 'camelot-lattice')
    settings_by_engine: dict[str, dict[str, Any]] = field(default_factory=dict)
    overlap_threshold: float = 0.5
    grid_tolerance_points: float = 2.0
    min_source_coverage: float = 0.95
    min_spatial_agreement: float = 0.95
    min_cell_density: float = 0.3
    render: bool = True
    resolution: int = 150
    min_text_characters: int = 40
    max_suspect_ratio: float = 0.02
    strip_normalized_text: bool = False
    number_profile: str = 'auto'
    header_search_lines: float = 8
    header_max_gap_lines: float = 3
    header_horizontal_margin: float = 12
    header_line_tolerance: float = 3

    def __post_init__(self):
        if self.pages is not None and (not self.pages or any(not isinstance(p,int) or isinstance(p,bool) for p in self.pages)):
            raise ValueError('pages must be a nonempty sequence of integer page numbers')
        if min(self.header_search_lines,self.header_max_gap_lines) <= 0 or min(self.header_horizontal_margin,self.header_line_tolerance) < 0:
            raise ValueError('Header search/gap must be positive; margin/tolerance nonnegative')
        from .numbers import PROFILES
        if self.number_profile not in ('auto', *PROFILES):
            raise ValueError(f'Unknown number profile: {self.number_profile}')
        if not self.engines or len(set(self.engines)) != len(self.engines):
            raise ValueError('Engine routes must be nonempty and unique')
        if any(e in ('auto', 'compare') for e in self.engines):
            raise ValueError('Engine routes cannot contain orchestration modes')
        if self.grid_tolerance_points < 0:
            raise ValueError('Grid tolerance must be nonnegative')
        for value in (self.overlap_threshold,self.min_source_coverage,self.min_spatial_agreement,self.min_cell_density):
            if not 0 < value <= 1:
                raise ValueError('Ranking thresholds must be in (0, 1]')
        if self.resolution <= 0 or self.min_text_characters < 0:
            raise ValueError('Resolution must be positive and text threshold nonnegative')
        if not 0 <= self.max_suspect_ratio <= 1:
            raise ValueError('Suspect ratio must be between 0 and 1')
