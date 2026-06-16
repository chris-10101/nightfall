from html import escape


UNSUBSCRIBE_MARKERS = (
    "reply unsubscribe",
    "unsubscribe:",
    "unsubscribe here",
    "not contact you again",
)


def plain_unsubscribe_footer(unsubscribe_text: str, unsubscribe_target: str) -> str:
    if not unsubscribe_target:
        return unsubscribe_text.strip()
    return f"If this is not relevant, you can unsubscribe here and I will not contact you again.\nUnsubscribe: {unsubscribe_target}"


def strip_existing_unsubscribe_text(body: str) -> str:
    paragraphs = body.rstrip().split("\n\n")
    kept = []
    for paragraph in paragraphs:
        normalized = " ".join(paragraph.lower().split())
        if any(marker in normalized for marker in UNSUBSCRIBE_MARKERS):
            continue
        kept.append(paragraph.strip("\n"))
    return "\n\n".join(paragraph for paragraph in kept if paragraph.strip()).rstrip()


def text_to_html_paragraphs(text: str) -> str:
    paragraphs = []
    for block in text.strip().split("\n\n"):
        escaped_lines = [escape(line) for line in block.splitlines()]
        paragraphs.append(f"<p>{'<br>'.join(escaped_lines)}</p>")
    return "\n".join(paragraphs)


def html_with_unsubscribe_link(body: str, unsubscribe_text: str, unsubscribe_url: str) -> str:
    base_body = strip_existing_unsubscribe_text(body)
    html = text_to_html_paragraphs(base_body)
    if not unsubscribe_url:
        return html
    link = f'<a href="{escape(unsubscribe_url, quote=True)}">unsubscribe here</a>'
    footer = (
        "If this is not relevant, you can "
        f"{link} and I will not contact you again."
    )
    return f"{html}\n<p>{footer}</p>"
