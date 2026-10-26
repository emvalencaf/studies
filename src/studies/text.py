import html
import re


def option_to_markdown(option_html: str) -> str:
    """Opções da Udemy vêm em HTML; st.radio/st.checkbox só renderizam Markdown."""
    s = re.sub(r"</?(code|pre)>", "`", option_html)
    s = re.sub(r"<br\s*/?>", " ", s)
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(s).strip()
