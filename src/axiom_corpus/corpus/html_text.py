"""HTML defaults shared by the Maine and Ohio operative-text readers.

These are DOM exclusions, not a CSS renderer: inline styles and CSS classes
may collapse operative text, so they do not determine body presence.
"""

from collections.abc import Iterable
from unicodedata import category

from bs4.element import PageElement, Tag

_NONRENDERED = frozenset(
    {
        "template",
        "script",
        "style",
        "noscript",
        "head",
        "title",
        "iframe",
        "object",
        "datalist",
        "noembed",
        "noframes",
        "frameset",
        "audio",
        "video",
        "canvas",
        "rp",
    }
)


def is_nonrendered_element(node: Tag) -> bool:
    """Identify excluded HTML defaults, including a closed disclosure's body."""
    if node.name in _NONRENDERED or (node.name == "dialog" and not node.has_attr("open")):
        return True
    if node.name == "desc" and node.find_parent("svg") is not None:
        return True
    if node.name in {"annotation", "annotation-xml"} and node.find_parent("math") is not None:
        return True
    parent = node.parent
    return (
        isinstance(parent, Tag)
        and parent.name == "details"
        and not parent.has_attr("open")
        and node is not parent.find("summary", recursive=False)
    )


def statute_text_children(node: Tag) -> Iterable[PageElement]:
    """A closed details element displays only its first direct summary."""
    if node.name == "details" and not node.has_attr("open"):
        summary = node.find("summary", recursive=False)
        return (summary,) if summary is not None else ()
    return node.children


def has_statute_text(text: str) -> bool:
    """Ignore whitespace and invisible formatting without altering actual text."""
    # Variation selectors and a few zero-width combining characters have the
    # Mn category. Ordinary combining marks can display a glyph and still count.
    return any(
        not char.isspace()
        and category(char) != "Cf"
        and char not in "\u034f\u17b4\u17b5\u180b\u180c\u180d\u180f"
        and not "\ufe00" <= char <= "\ufe0f"
        and not "\U000e0100" <= char <= "\U000e01ef"
        for char in text
    )
