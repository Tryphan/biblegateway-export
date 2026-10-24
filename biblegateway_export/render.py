"""Render the same passage model directly into Markdown, Org, or plain text."""
from dataclasses import dataclass
import re

from .model import Inline, Passage


@dataclass(frozen=True)
class Options:
    format: str = "markdown"
    boldwords: bool = False
    copyright: bool = True
    headers: bool = True
    footnotes: bool = True
    crossrefs: bool = True
    numbering: bool = True
    newline: bool = False


class Renderer:
    def __init__(self, options: Options):
        self.options = options
        self.org = options.format == "org"
        self.txt = options.format == "txt"

    def heading(self, level: int, text: str) -> str:
        if self.txt:
            return text
        return ("*" if self.org else "#") * level + " " + text

    def note_ref(self, label: str) -> str:
        if self.txt:
            return f"[{label}]"
        return f"[fn:{label}]" if self.org else f"[^{label}]"

    def inline(self, children: tuple[Inline, ...], active: str = "") -> str:
        output = []
        for node in children:
            kind = node.kind
            if kind == "text":
                output.append(node.value)
            elif kind == "break":
                output.append("\n" if self.txt else " \\\\\n" if self.org else "  \n")
            elif kind in {"footnote", "crossref"}:
                if getattr(self.options, "footnotes" if kind == "footnote" else "crossrefs"):
                    output.append(self.note_ref(node.value))
            elif kind in {"verse", "chapter"}:
                if not self.options.numbering:
                    continue
                if self.options.newline:
                    if kind == "chapter":
                        output.append("\n" + self.heading(5, f"Chapter {node.value}") + "\n"
                                      + self.heading(6, "1") + " ")
                    else:
                        output.append("\n" + self.heading(6, node.value) + " ")
                else:
                    output.append(node.value + (":1 " if kind == "chapter" else " "))
            else:
                bold = kind == "bold" or (kind == "words" and self.options.boldwords)
                emphasis = "bold" if bold else "italic" if kind == "italic" else ""
                value = self.inline(node.children, emphasis or active)
                if not self.txt and emphasis and emphasis != active and value.strip():
                    mark = ("*" if self.org else "**") if bold else ("/" if self.org else "_")
                    value = self.emphasize(value, mark)
                output.append(value)
        return "".join(output)

    @staticmethod
    def emphasize(value: str, mark: str) -> str:
        """Keep verse headings and hard breaks outside emphasis delimiters."""
        result = []
        for line in value.splitlines(keepends=True):
            newline = "\n" if line.endswith("\n") else ""
            content = line.removesuffix("\n")
            heading = re.match(r"^([#*]{5,6} (?:Chapter )?\d+(?:-\d+)?)(.*)$", content)
            prefix = heading[1] if heading else ""
            content = heading[2] if heading else content
            hardbreak = " \\\\" if content.endswith(" \\\\") else ""
            if hardbreak:
                content = content[:-len(hardbreak)]
            leading = content[:len(content) - len(content.lstrip())]
            trailing = content[len(content.rstrip()):]
            body = content.strip()
            result.append(prefix + leading + (mark + body + mark if body else "")
                          + trailing + hardbreak + newline)
        return "".join(result)

    def render(self, passage: Passage) -> str:
        sections = [self.heading(1, f"{passage.reference} ({passage.translation})")]
        for block in passage.blocks:
            if block.kind == "heading" and not self.options.headers:
                continue
            text = self.inline(block.children).strip()
            if text:
                sections.append(self.heading(2, text) if block.kind == "heading" else text)
        for title, notes, enabled in (
            ("Footnotes", passage.footnotes, self.options.footnotes),
            ("Crossrefs", passage.crossrefs, self.options.crossrefs),
        ):
            if enabled and notes:
                definitions = [self.note_ref(note.label) + (" " if self.org or self.txt else ": ")
                               + self.inline(note.children).strip() for note in notes]
                sections.append(self.heading(3, title) + "\n" + "\n".join(definitions))
        if self.options.copyright:
            sections.extend(self.inline(block.children).strip() for block in passage.copyright)
        return "\n\n".join(sections).rstrip() + "\n"
