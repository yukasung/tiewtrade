from collections.abc import Callable
from dataclasses import replace
from typing import cast


def replace_unchecked[T](instance: T, **changes: object) -> T:
    unchecked_replace = cast(Callable[..., T], replace)
    return unchecked_replace(instance, **changes)
