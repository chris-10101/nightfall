from html import escape


def plain_unsubscribe_footer(unsubscribe_text: str, unsubscribe_target: str) -> str:
    if not unsubscribe_target:
        return unsubscribe_text.strip()
    return f"{unsubscribe_text.strip()}\nUnsubscribe: {unsubscribe_target}"


def strip_plain_unsubscribe_footer(body: str) -> str:
    lines = body.rstrip().splitlines()
    while lines and not lines[-1].strip():
        lines.pop()
    if lines and lines[-1].strip().lower().startswith("unsubscribe:"):
        lines.pop()
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines).rstrip()


def text_to_html_paragraphs(text: str) -> str:
    paragraphs = []
    for block in text.strip().split("\n\n"):
        escaped_lines = [escape(line) for line in block.splitlines()]
        paragraphs.append(f"<p>{'<br>'.join(escaped_lines)}</p>")
    return "\n".join(paragraphs)


def html_with_unsubscribe_link(body: str, unsubscribe_text: str, unsubscribe_url: str) -> str:
    base_body = strip_plain_unsubscribe_footer(body)
    html = text_to_html_paragraphs(base_body)
    if not unsubscribe_url:
        return html
    link = f'<a href="{escape(unsubscribe_url, quote=True)}">unsubscribe here</a>'
    footer = (
        "If this is not relevant, you can "
        f"{link} and I will not contact you again."
    )
    return f"{html}\n<p>{footer}</p>"
