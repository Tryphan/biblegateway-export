"""Extract passage structure from HTML; no output-format syntax is generated here."""
import re

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

from .model import Block, Inline, Note, Passage


class PassageError(ValueError):
    """The page does not contain a supported, unambiguous passage."""


def plain(node: Tag) -> str:
    return " ".join(node.get_text(" ", strip=True).split())


def label_from_id(value: str) -> str:
    match = re.search(r"([A-Za-z]+)$", value)
    return match[1] if match else ""


def reference_label(node: Tag) -> str:
    anchor = node.find("a")
    if anchor:
        label = plain(anchor).strip("[]() ")
        if re.fullmatch(r"[A-Za-z]+", label):
            return label
    # Some versions put the label only in data attributes or accessible text.
    match = re.search(r"See (?:footnote|cross-reference) ([A-Za-z]+)",
                      str(node), re.IGNORECASE)
    if match:
        return match[1]
    return label_from_id(str(node.get("data-fn") or node.get("data-cr") or ""))


def inline_children(node: Tag) -> tuple[Inline, ...]:
    result = []
    for child in node.children:
        if isinstance(child, Comment):
            continue
        if isinstance(child, NavigableString):
            # HTML layout whitespace is not a line break in the passage.
            value = re.sub(r"\s+", " ", str(child))
            result.append(Inline("text", value))
            continue
        if not isinstance(child, Tag) or child.name in {"script", "style", "h1", "h2", "hr"}:
            continue
        classes = child.get("class", [])
        if "versenum" in classes:
            result.append(Inline("verse", plain(child)))
        elif "chapternum" in classes:
            result.append(Inline("chapter", plain(child)))
        elif child.name == "sup" and ("footnote" in classes or child.has_attr("data-fn")):
            label = reference_label(child)
            if not label:
                raise PassageError("Could not read a footnote label in the passage")
            result.append(Inline("footnote", label))
        elif child.name == "sup" and ("crossreference" in classes or child.has_attr("data-cr")):
            label = reference_label(child)
            if not label:
                raise PassageError("Could not read a cross-reference label in the passage")
            result.append(Inline("crossref", label))
        elif child.name == "br":
            result.append(Inline("break"))
        elif "small-caps" in classes or "font-variant: small-caps" in child.get("style", ""):
            result.append(Inline("text", plain(child).upper()))
        elif child.name in {"b", "strong", "i", "em"} or "woj" in classes:
            kind = "words" if "woj" in classes else (
                "bold" if child.name in {"b", "strong"} else "italic")
            result.append(Inline(kind, children=inline_children(child)))
        else:
            # Keep link text and unknown wrappers without leaking HTML.
            result.extend(inline_children(child))
    return tuple(result)


def alphabetical(index: int, uppercase: bool = False) -> str:
    """Zero-based a..z, aa..az.. labels, without a fixed upper limit."""
    result = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(ord("a") + remainder) + result
    return result.upper() if uppercase else result


def extract_notes(root: Tag, crossrefs: bool = False) -> tuple[Note, ...]:
    selector = "a.crossref-link" if crossrefs else ".footnote-text"
    notes = []
    seen = set()
    for node in root.select(selector):
        item = node.find_parent("li")
        if item is None or id(item) in seen:
            continue
        seen.add(id(item))
        label = label_from_id(str(item.get("id", ""))) or alphabetical(len(notes), crossrefs)
        children = inline_children(node)
        if not crossrefs:
            prefix = item.find("a")
            if prefix is not None and prefix not in node.descendants:
                children = (Inline("text", plain(prefix) + " "),) + children
        else:
            # A cross-reference definition may contain several links and text.
            links = item.select("a.crossref-link")
            parts = []
            for link in links:
                if parts:
                    parts.append(Inline("text", "; "))
                parts.extend(inline_children(link))
            children = tuple(parts)
        notes.append(Note(label, children))
    return tuple(notes)


def has_text(children: tuple[Inline, ...]) -> bool:
    """Require actual passage text, not just a verse marker or footnote."""
    return any((node.kind == "text" and bool(node.value.strip())) or has_text(node.children)
               for node in children)


def parse_passage(html: str, reference: str = "", translation: str = "NET") -> Passage:
    soup = BeautifulSoup(html, "html.parser")
    # Never let footer headings, menus, adverts, or scripts become passage text.
    for node in soup.select("footer, script, style, .other-resources, .sponsors, "
                            "section.other-resources, section.sponsors"):
        node.decompose()
    containers = soup.select(".passage-content")
    if len(containers) > 1:
        raise PassageError("Multiple passages/translations are not supported; request one at a time")
    root = containers[0] if containers else soup
    if not containers:
        # Support legacy pages and compact saved fixtures, but require a passage
        # title and verse markup to avoid exporting an error page or navigation.
        if not soup.select_one("h1.passage-display") or not soup.select_one(
                ".text, .chapternum, .versenum"):
            raise PassageError("No Bible passage found; check the reference and translation")
        for title in list(soup.select("h1.passage-display")):
            for sibling in list(title.previous_siblings):
                sibling.extract()
    title = soup.select_one(".passage-display")
    if title:
        ref = title.select_one(".passage-display-bcv, .bcv")
        version = title.select_one(".passage-display-version, .translation")
        if ref:
            reference = plain(ref)
        if version:
            translation = plain(version)
    blocks = []
    for node in root.find_all(["p", "h3"]):
        # Exclude notes and copyright from the main body even when nested inside
        # the same passage-content wrapper.
        if node.find_parent(["li", "p", "h3"]):
            continue
        if any("footnotes" in parent.get("class", [])
               or "crossrefs" in parent.get("class", [])
               or any(c.startswith("publisher-info") for c in parent.get("class", []))
               for parent in node.parents if isinstance(parent, Tag)):
            continue
        if node.name == "h3" and plain(node) == "More on the NIV":
            continue
        if not containers and node.name == "p" and not node.select_one(
                ".text, .chapternum, .versenum"):
            continue
        content = inline_children(node)
        if any(part.kind != "text" or part.value.strip() for part in content):
            blocks.append(Block("heading" if node.name == "h3" else "paragraph", content))
    if not any(block.kind == "paragraph" and has_text(block.children) for block in blocks):
        raise PassageError("No Bible passage text found; BibleGateway markup may have changed")
    # Metadata sometimes sits outside passage-content, but inside passage-text.
    scope = (root.find_parent(class_="passage-box")
             or root.find_parent(class_="passage-table")
             or root.find_parent(class_="passage-text")) if containers else soup
    scope = scope or root
    copyrights = []
    for node in scope.select('[class*="publisher-info"] p'):
        copyrights.append(Block("paragraph", inline_children(node)))
    return Passage(reference, translation, tuple(blocks), extract_notes(scope),
                   extract_notes(scope, True), tuple(copyrights))
