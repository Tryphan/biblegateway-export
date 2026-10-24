"""Format-independent passage data shared by the parser and renderers."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Inline:
    kind: str
    value: str = ""
    children: tuple["Inline", ...] = ()


@dataclass(frozen=True)
class Block:
    kind: str
    children: tuple[Inline, ...]


@dataclass(frozen=True)
class Note:
    label: str
    children: tuple[Inline, ...]


@dataclass(frozen=True)
class Passage:
    reference: str
    translation: str
    blocks: tuple[Block, ...]
    footnotes: tuple[Note, ...] = ()
    crossrefs: tuple[Note, ...] = ()
    copyright: tuple[Block, ...] = ()
