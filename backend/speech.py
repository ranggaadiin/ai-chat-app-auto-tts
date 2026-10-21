"""Ubah teks (terutama yang ada kodenya) jadi naskah yang enak didengar.

Dipakai dua cara:
1. Model diminta bikin naskah suara sendiri (bagian setelah ===SUARA===).
2. Kalau model nggak ngikutin format, teks tampilan diubah otomatis di sini.
"""
import re

DELIMITER = re.compile(r"\n?[ \t]*={2,}[ \t]*SUARA[ \t]*={2,}[ \t]*\n?", re.I)

# Urutan penting: simbol yang lebih panjang dulu
SYMBOLS = {
    "===": " sama persis dengan ",
    "!==": " tidak sama persis dengan ",
    "=>": " panah ",
    "->": " panah ",
    "==": " sama dengan ",
    "!=": " tidak sama dengan ",
    ">=": " lebih besar sama dengan ",
    "<=": " lebih kecil sama dengan ",
    "&&": " dan ",
    "||": " atau ",
    "++": " tambah tambah ",
    "--": " kurang kurang ",
    "::": " titik dua titik dua ",
    "()": " kurung buka tutup ",
    "{}": " kurung kurawal buka tutup ",
    "[]": " kurung siku buka tutup ",
    "(": " kurung buka ",
    ")": " kurung tutup ",
    "{": " kurung kurawal buka ",
    "}": " kurung kurawal tutup ",
    "[": " kurung siku buka ",
    "]": " kurung siku tutup ",
    ";": " titik koma ",
    ":": " titik dua ",
    ",": " koma ",
    "=": " sama dengan ",
    "+": " tambah ",
    "-": " kurang ",
    "*": " kali ",
    "/": " garis miring ",
    "%": " persen ",
    "!": " tanda seru ",
    "<": " lebih kecil dari ",
    ">": " lebih besar dari ",
    "#": " pagar ",
    "@": " at ",
    "$": " dolar ",
    '"': " kutip ",
    "'": " kutip ",
    "\\": " backslash ",
    "|": " pipa ",
    "&": " dan ",
    "^": " pangkat ",
    "~": " ",
    "`": " ",
}
_SYMBOL_RE = re.compile("|".join(re.escape(s) for s in sorted(SYMBOLS, key=len, reverse=True)))

FILE_EXT = r"py|js|jsx|ts|tsx|json|md|html|css|env|yaml|yml|sh|txt|sql|go|java|toml|lock"


def split_reply(reply: str):
    """Pisah jawaban model jadi (teks tampilan, naskah suara atau None)."""
    parts = DELIMITER.split(reply, maxsplit=1)
    display = parts[0].strip()
    speech = parts[1].strip() if len(parts) > 1 else ""
    return display, (speech or None)


def verbalize_code(code: str, max_chars: int = 600) -> str:
    """Bacakan kode: pecah camelCase/snake_case, sebut nama simbol."""
    code = re.sub(r"__(\w+)__", r" dunder \1 ", code)
    code = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", code)  # camelCase
    code = re.sub(r"(?<=\w)_(?=\w)", " ", code)  # snake_case
    code = re.sub(r"(?<=\w)-(?=[a-zA-Z])", " ", code)  # kebab-case
    code = re.sub(r"(?<=[\w)\]])\.(?=\w)", " titik ", code)  # a.b.c, foo().bar
    code = code.replace("\n", " . ")
    code = _SYMBOL_RE.sub(lambda m: SYMBOLS[m.group(0)], code)
    code = re.sub(r"\s+", " ", code).strip()
    if len(code) > max_chars:
        code = code[:max_chars].rsplit(" ", 1)[0] + " dan seterusnya"
    return code


def speech_from_display(text: str) -> str:
    """Fallback: ubah teks tampilan (markdown + kode) jadi naskah bicara."""

    def fenced(m):
        lang = (m.group(1) or "").strip()
        label = f"bahasa {lang}" if lang else "kode"
        return f" . Ada blok {label}. {verbalize_code(m.group(2))} . Selesai blok kode. "

    text = re.sub(r"```([\w+#-]*)[ \t]*\n?(.*?)```", fenced, text, flags=re.S)
    text = re.sub(r"`([^`\n]+)`", lambda m: " " + verbalize_code(m.group(1), 120) + " ", text)
    return text


def clean_for_speech(text: str) -> str:
    text = speech_from_display(text)
    text = re.sub(r"https?://\S+", "link", text)
    text = re.sub(rf"\b([\w-]+)\.({FILE_EXT})\b", r"\1 titik \2", text)
    text = re.sub(rf"(?<!\w)\.({FILE_EXT}|gitignore)\b", r"titik \1", text)
    text = re.sub(r"^\s*([-*]|\d+\.)\s+", "", text, flags=re.M)  # bullet / nomor list
    text = re.sub(r"[*#>~|]", " ", text)
    text = re.sub(r"(?<=\w)_(?=\w)", " ", text)
    text = text.replace("_", " ")
    return re.sub(r"\s+", " ", text).strip()
