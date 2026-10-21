import asyncio
import base64
import io
import os
import re

import edge_tts
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from gtts import gTTS
from openai import OpenAI

from speech import clean_for_speech, speech_from_display, split_reply

load_dotenv()

app = Flask(__name__)
# Isi ALLOWED_ORIGINS dengan URL frontend (pisah koma), mis. https://ai-chat.vercel.app
origins = [o.strip() for o in os.getenv("https://ai-chat-app-auto-tts-qsez.vercel.app", "*").split(",") if o.strip()]
CORS(app, origins=origins)

# Semua provider di bawah gratis dan kompatibel OpenAI.
# Provider cuma aktif kalau API key-nya diisi di env.
PROVIDERS = {
    "groq": {  # console.groq.com/keys
        "key_env": "GROQ_API_KEY",
        "base_url": "https://api.groq.com/openai/v1",
    },
    "gemini": {  # aistudio.google.com/apikey
        "key_env": "GEMINI_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
    },
}

# Daftar model yang bisa dipilih dari frontend (free tier).
# Cek daftar terbaru: console.groq.com/docs/models dan ai.google.dev/gemini-api/docs/pricing
ALL_MODELS = [
    {"id": "llama-3.1-8b-instant", "label": "Llama 3.1 8B (Groq, paling cepat)", "provider": "groq"},
    {"id": "llama-3.3-70b-versatile", "label": "Llama 3.3 70B (Groq, seimbang)", "provider": "groq"},
    {"id": "openai/gpt-oss-120b", "label": "GPT-OSS 120B (Groq, pintar)", "provider": "groq"},
    {"id": "gemini-3.5-flash-lite", "label": "Gemini 3.5 Flash-Lite (Google, ringan)", "provider": "gemini"},
    {"id": "gemini-3.8-flash", "label": "Gemini 3.8 Flash (Google, pintar)", "provider": "gemini"},
]

clients = {
    name: OpenAI(api_key=os.getenv(cfg["key_env"]), base_url=cfg["base_url"])
    for name, cfg in PROVIDERS.items()
    if os.getenv(cfg["key_env"])
}

# Hanya tampilkan model dari provider yang key-nya ada
MODELS = [
    {"id": m["id"], "label": m["label"]} for m in ALL_MODELS if m["provider"] in clients
]
MODEL_PROVIDER = {m["id"]: m["provider"] for m in ALL_MODELS if m["provider"] in clients}
MODEL_IDS = set(MODEL_PROVIDER)
DEFAULT_MODEL = (
    "llama-3.3-70b-versatile" if "llama-3.3-70b-versatile" in MODEL_IDS
    else (MODELS[0]["id"] if MODELS else None)
)

SYSTEM_PROMPT = """Kamu asisten AI yang ngobrol santai pakai bahasa Indonesia, jago soal coding.
Jawabanmu dipakai dua cara: ditampilkan di layar dan dibacakan sebagai suara. User sering NGGAK melihat layar, jadi suara harus bisa dipahami sendiri.

FORMAT WAJIB, dua bagian dipisah satu baris persis berisi ===SUARA===

Bagian 1 (layar): jawaban normal. Boleh markdown, blok kode pakai tiga backtick plus nama bahasa, dan daftar. Singkat dan jelas.

===SUARA===

Bagian 2 (suara): naskah yang akan dibacakan keras. Aturan:
- Jangan bacakan kode mentah. Jelaskan kode pakai kata-kata: mulai dari tujuan kode secara garis besar, lalu alurnya langkah demi langkah ("pertama", "lalu", "terakhir").
- Sebut nama fungsi, variabel, atau file yang penting dengan jelas, dan sebut nama bahasa atau library-nya. Nama file ditulis seperti diucapkan, misalnya "app titik py".
- Sebut simbol hanya kalau penting untuk memahami, pakai namanya (kurung kurawal, titik dua, panah). Jangan eja satu per satu.
- Kalimat pendek, satu ide per kalimat. Hindari tabel, bullet, markdown, emoji, dan URL.
- Kalau kodenya panjang, jelaskan gambaran besarnya lalu tawarkan untuk dirinci per bagian.
- Kalau user cuma ngobrol biasa tanpa kode, bagian suara boleh sama dengan bagian layar tapi tanpa markdown.
- Istilah teknis Inggris (function, array, endpoint) boleh dipakai apa adanya.
Selalu tulis kedua bagian, jangan lupa baris ===SUARA===."""





# Suara Microsoft Edge neural (gratis, tanpa API key). Pilihan Indonesia:
# id-ID-GadisNeural (cewek), id-ID-ArdiNeural (cowok)
TTS_VOICE = os.getenv("TTS_VOICE", "id-ID-GadisNeural")
# Sedikit lebih pelan biar penjelasan kode gampang diikuti. Mis. "+10%" buat lebih cepat
TTS_RATE = os.getenv("TTS_RATE", "-5%")


async def _edge_tts(text: str) -> bytes:
    audio = b""
    async for chunk in edge_tts.Communicate(text, TTS_VOICE, rate=TTS_RATE).stream():
        if chunk["type"] == "audio":
            audio += chunk["data"]
    if not audio:
        raise RuntimeError("Edge TTS ngasih audio kosong")
    return audio


def synthesize(text: str, lang: str = "id") -> str:
    """Return audio mp3 sebagai base64. Edge TTS dulu, gTTS kalau gagal."""
    text = clean_for_speech(text)
    try:
        data = asyncio.run(_edge_tts(text))
    except Exception as e:
        app.logger.warning("Edge TTS gagal (%s), pindah ke gTTS", e)
        buf = io.BytesIO()
        gTTS(text=text, lang=lang).write_to_fp(buf)
        data = buf.getvalue()
    return base64.b64encode(data).decode("utf-8")


@app.get("/api/models")
def list_models():
    return jsonify({"models": MODELS, "default": DEFAULT_MODEL})


@app.post("/api/chat")
def chat():
    data = request.get_json(silent=True) or {}
    messages = data.get("messages", [])
    model = data.get("model", DEFAULT_MODEL)

    if model not in MODEL_IDS:
        return jsonify({"error": "Model tidak dikenal"}), 400
    if not messages or messages[-1].get("role") != "user":
        return jsonify({"error": "Pesan terakhir harus dari user"}), 400

    try:
        res = clients[MODEL_PROVIDER[model]].chat.completions.create(
            model=model,
            max_tokens=2048,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}]
            + [{"role": m["role"], "content": m["content"]} for m in messages],
        )
        raw = (res.choices[0].message.content or "").strip()
    except Exception as e:
        return jsonify({"error": f"Gagal manggil AI: {e}"}), 502

    # display = teks di layar, speech = naskah yang dibacakan.
    # Kalau model nggak ngasih naskah suara, dibikin otomatis dari teks layar.
    display, speech = split_reply(raw)
    speech = speech or speech_from_display(display)

    # Suara dibuat terpisah-gagal TTS jangan bikin teks ikut hilang
    audio = None
    try:
        audio = synthesize(speech)
    except Exception as e:
        app.logger.warning("TTS gagal: %s", e)

    return jsonify({"reply": display, "speech": speech, "audio": audio, "model": model})


@app.post("/api/tts")
def tts():
    """Dipakai kalau audio perlu dibuat ulang (mis. TTS sempat gagal)."""
    text = (request.get_json(silent=True) or {}).get("text", "").strip()
    if not text:
        return jsonify({"error": "Teks kosong"}), 400
    try:
        return jsonify({"audio": synthesize(text)})
    except Exception as e:
        return jsonify({"error": f"TTS gagal: {e}"}), 502


if __name__ == "__main__":
    app.run(port=int(os.getenv("PORT", 5000)), debug=os.getenv("FLASK_DEBUG") == "1")
