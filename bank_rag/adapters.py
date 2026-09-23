"""
Adapter registry for institution-specific page cleaning.

Most bank websites can be handled by the generic cleaner in scrape.py
(default_clean). If a particular site's markup defeats the generic
cleaner (content buried in odd divs, JS-rendered tabs, etc.), write a
dedicated function here and reference it by name in
config/institutions.yaml under that institution's "adapter" field.

Every adapter function has the same signature:
    def my_adapter(soup: BeautifulSoup) -> str
It receives the parsed page and must return the cleaned, human-readable
text to store and chunk.
"""

from bs4 import BeautifulSoup


def default_clean(soup: BeautifulSoup) -> str:
    """Generic cleaner: strip nav/boilerplate, keep the main content text.
    Good enough for most straightforward bank pages."""
    for tag in soup(["script", "style", "nav", "header", "footer", "aside",
                      "noscript", "form", "iframe"]):
        tag.decompose()

    # Drop common boilerplate containers by class/id keyword.
    boilerplate_keywords = ["nav", "menu", "footer", "header", "cookie",
                             "sidebar", "breadcrumb", "social", "banner"]
    for tag in soup.find_all(True):
        attrs = " ".join(tag.get("class", []) + [tag.get("id", "")]).lower()
        if any(kw in attrs for kw in boilerplate_keywords):
            tag.decompose()

    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = main.get_text(separator="\n")

    # Collapse excess blank lines/whitespace left after stripping tags.
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n\n".join(lines)


# Register additional adapters here as needed, e.g.:
# def ameriabank_clean(soup: BeautifulSoup) -> str:
#     ...custom logic for a page that default_clean handles poorly...
#     return text

ADAPTERS = {
    "default": default_clean,
    # "ameriabank_custom": ameriabank_clean,
}


def get_adapter(name: str):
    if name not in ADAPTERS:
        raise ValueError(
            f"Unknown adapter '{name}'. Available: {list(ADAPTERS.keys())}. "
            f"Add it to adapters.py or use 'default' in institutions.yaml."
        )
    return ADAPTERS[name]
