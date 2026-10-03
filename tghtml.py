"""Telegram HTML formatlash: xavfsiz tozalash (sanitize) va oddiy matnga aylantirish.

Mini app'da operator matnni qalin/kursiv/... qilib yuboradi yoki o'zi <b>Ozodbek</b> deb yozadi.
Bu modul faqat Telegram qo'llaydigan teglarni qoldiradi, qolganini oddiy matn sifatida
ekranlaydi va ochiq qolgan teglarni yopadi. Natija parse_mode=HTML bilan xavfsiz yuboriladi.
"""
import html
import re
from html.parser import HTMLParser

# kiruvchi teg -> Telegram tegi
_MAP = {
    "b": "b", "strong": "b",
    "i": "i", "em": "i",
    "u": "u", "ins": "u",
    "s": "s", "strike": "s", "del": "s",
    "code": "code", "pre": "pre",
    "tg-spoiler": "tg-spoiler",
    "blockquote": "blockquote",
    "a": "a",
}
_SAFE_HREF = re.compile(r"^(https?://|tg://|mailto:|tel:)", re.I)


class _Clean(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.stack = []          # ochiq Telegram teglari

    # --- yordamchilar ---
    def _literal(self):
        raw = self.get_starttag_text() or ""
        self.out.append(html.escape(raw, quote=False))

    def _in_code(self):
        return any(t in ("code", "pre") for t in self.stack)

    def _close(self, tg):
        if tg not in self.stack:
            return
        while self.stack:
            t = self.stack.pop()
            self.out.append(f"</{t}>")
            if t == tg:
                break

    # --- HTMLParser ---
    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "br":
            self.out.append("\n")
            return
        if tag == "span" and any(k == "class" and "tg-spoiler" in (v or "") for k, v in attrs):
            tg = "tg-spoiler"
        else:
            tg = _MAP.get(tag)
        if not tg or self._in_code():
            self._literal()
            return
        # <b>Ozodbek<b> — bir xil teg ikkinchi marta ochilsa, yopish deb tushunamiz
        if tg in self.stack and tg != "a":
            self._close(tg)
            return
        if tg == "a":
            href = dict(attrs).get("href") or ""
            if not _SAFE_HREF.match(href.strip()):
                self._literal()
                return
            self.stack.append("a")
            self.out.append(f'<a href="{html.escape(href.strip(), quote=True)}">')
            return
        self.stack.append(tg)
        self.out.append(f"<{tg}>")

    def handle_startendtag(self, tag, attrs):
        if tag.lower() == "br":
            self.out.append("\n")
        else:
            self._literal()

    def handle_endtag(self, tag):
        tag = tag.lower()
        tg = "tg-spoiler" if tag == "span" and "tg-spoiler" in self.stack else _MAP.get(tag)
        if tg and tg in self.stack and (not self._in_code() or tg in ("code", "pre")):
            self._close(tg)
        elif tg and self._in_code():
            self.out.append(html.escape(f"</{tag}>", quote=False))
        elif tg is None and tag not in ("p", "div", "span"):
            self.out.append(html.escape(f"</{tag}>", quote=False))

    def handle_data(self, data):
        self.out.append(html.escape(data, quote=False))

    def handle_comment(self, data):
        pass

    def finish(self):
        self.close()
        while self.stack:
            self.out.append(f"</{self.stack.pop()}>")
        return "".join(self.out)


def sanitize(raw: str) -> str:
    """Faqat Telegram teglarini qoldiradi, qolganini ekranlaydi, ochiq teglarni yopadi."""
    if not raw:
        return ""
    p = _Clean()
    try:
        p.feed(str(raw))
        res = p.finish()
    except Exception:
        return html.escape(str(raw), quote=False)
    # bo'sh teglarni olib tashlaymiz (<b></b>)
    prev = None
    while prev != res:
        prev = res
        res = re.sub(r"<(b|i|u|s|code|pre|tg-spoiler|blockquote)></\1>", "", res)
    return res.strip("\n") if res.strip() else ""


def to_plain(tg_html: str) -> str:
    """Telegram HTML -> oddiy matn (qidiruv, ko'rinish, kanal uchun)."""
    if not tg_html:
        return ""
    return html.unescape(re.sub(r"<[^>]+>", "", tg_html))


def has_markup(tg_html: str) -> bool:
    return bool(tg_html) and bool(re.search(r"<(b|i|u|s|code|pre|tg-spoiler|blockquote|a)\b", tg_html))


def from_message(message) -> str | None:
    """Telegram xabaridagi formatlashni (entities) HTML ko'rinishida qaytaradi; bo'lmasa None."""
    try:
        ents = message.entities or message.caption_entities
        if not ents:
            return None
        h = message.html_text
        return sanitize(h) if h and has_markup(h) else None
    except Exception:
        return None
