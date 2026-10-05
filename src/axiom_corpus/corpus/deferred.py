"""Exceptions held while streaming, to be raised where a whole-input pass would.

The streaming release paths compute derived values row by row, but the
whole-artifact code they replaced raised each error at a particular point of
a later pass. They keep an error as a :class:`DeferredError` and raise it at
that point, so the first error reported is unchanged.
"""

from __future__ import annotations


class DeferredError:
    """One exception, held without its traceback until it is raised.

    A traceback's frames keep their local variables alive, and those include
    the whole provision record or row, body and all. Dropping the traceback
    chain when the error is stored keeps a held error as small as its message,
    so holding one per row stays within compact per-row memory.
    """

    __slots__ = ("error",)

    def __init__(self, error: Exception) -> None:
        self.error = without_tracebacks(error)


def replayed[T](value: T | DeferredError) -> T:
    """Return ``value``, or raise the error it holds."""
    if isinstance(value, DeferredError):
        raise value.error
    return value


def without_tracebacks[E: BaseException](error: E) -> E:
    """Drop the traceback of ``error`` and of every exception chained to it."""
    pending: list[BaseException] = [error]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        current.__traceback__ = None
        for linked in (current.__cause__, current.__context__):
            if linked is not None:
                pending.append(linked)
    return error
