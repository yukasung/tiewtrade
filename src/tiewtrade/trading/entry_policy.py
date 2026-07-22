from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EntryPolicy:
    max_entries: int

    def __post_init__(self) -> None:
        if not 2 <= self.max_entries <= 20 or self.max_entries % 2:
            raise ValueError("max_entries must be an even number between 2 and 20")
