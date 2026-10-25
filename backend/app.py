
import asyncio
import base64
import io
import os

import edge_tts
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from gtts import gTTS
from openai import OpenAI

from speech import clean_for_speech, speech_from_display, split_reply

load_dotenv()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024

# =====================================================
# CORS - FRONTEND VERCEL
# Render Environment:
# ALLOWED_ORIGINS=https://nama-app.vercel.app
# Jika lebih dari satu domain, pisahkan dengan koma.
# =====================================================
raw_origins = os.getenv("ALLOWED_ORIGINS", "")

origins = [
    origin.strip().rstrip("/")
    for origin in raw_origins.split(",")
    if origin.strip()
]

# Tambahkan localhost hanya saat development.
if os.getenv("FLASK_DEBUG") == "1":
    origins.extend([
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ])

# Hapus duplikat tanpa mengubah urutan.
origins = list(dict.fromkeys(origins))

CORS(
    app,
    resources={
        r"/api/*": {
            "origins": origins,
            "methods": ["GET", "POST", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
        }
    },
    supports_credentials=False,
    max_age=600,
)

# =====================================================
# PROVIDERS
# =====================================================
PROVIDERS = {
    "groq": {
        "key_env": "GROQ_API_KEY",
        "base_url": "https://api.groq.com/openai/v1",
    },
    "gemini": {
        "key_env": "GEMINI_API_KEY",
        "base_url": (
            "https://generativelanguage.googleapis.com/v1beta/openai/"
        ),
    },
}

# Pertahankan daftar model asli.
# Pastikan ID model masih tersedia di provider.
ALL_MODELS = [
    {
        "id": "llama-3.1-8b-instant",
        "label": "Llama 3.1 8B (Groq, paling cepat)",
        "provider": "groq",
    },
    {
        "id": "llama-3.3-70b-versatile",
        "label": "Llama 3.3 70B (Groq, seimbang)",
        "provider": "groq",
    },
    {
        "id": "openai/gpt-oss-120b",
        "label": "GPT-OSS 120B (Groq, pintar)",
        "provider": "groq",
    },
    {
        "id": "gemini-3.5-flash-lite",
        "label": "Gemini 3.5 Flash-Lite (Google, ringan)",
        "provider": "gemini",
    },
    {
        "id": "gemini-3.8-flash",
        "label": "Gemini 3.8 Flash (Google, pintar)",
        "provider": "gemini",
    },
]

# Aktifkan provider hanya jika API key terisi.
clients = {}

for name, config in PROVIDERS.items():
    api_key = os.getenv(config["key_env"], "").strip()

    if api_key:
        clients[name] = OpenAI(
            api_key=api_key,
            base_url=config["base_url"],
            timeout=60.0,
            max_retries=1,
        )

# Tampilkan model sesuai provider aktif.
MODELS = [
    {"id": model["id"], "label": model["label"]}
    for model in ALL_MODELS
    if model["provider"] in clients
]

MODEL_PROVIDER = {
    model["id"]: model["provider"]
    for model in ALL_MODELS
    if model["provider"] in clients
}

MODEL_IDS = set(MODEL_PROVIDER)

DEFAULT_MODEL = (
    "llama-3.3-70b-versatile"
    if "llama-3.3-70b-versatile" in MODEL_IDS
    else (MODELS[0]["id"] if MODELS else None)
)

# =====================================================
# SYSTEM PROMPT
# =====================================================
SYSTEM_PROMPT = """Kamu asisten AI yang ngobrol santai pakai bahasa Indonesia, jago soal coding.
Jawabanmu dipakai dua cara: ditampilkan di layar dan dibacakan sebagai suara.
User sering tidak melihat layar, jadi suara harus bisa dipahami sendiri.

FORMAT WAJIB, dua bagian dipisah satu baris persis berisi ===SUARA===

Bagian 1 (layar): jawaban normal. Boleh markdown, blok kode pakai tiga
backtick plus nama bahasa, dan daftar. Singkat dan jelas.

===SUARA===

Bagian 2 (suara): naskah yang akan dibacakan keras.
- Jangan bacakan kode mentah. Jelaskan tujuan kode secara garis besar,
  lalu alurnya langkah demi langkah.
- Sebut nama fungsi, variabel, file, bahasa, dan library yang penting.
- Kalimat pendek, satu ide per kalimat.
- Hindari tabel, bullet, markdown, emoji, dan URL.
- Kalau kodenya panjang, jelaskan gambaran besarnya.
- Kalau user ngobrol biasa, bagian suara boleh sama dengan bagian layar
  tetapi tanpa markdown.
- Istilah teknis Inggris boleh digunakan.
Selalu tulis kedua bagian dan jangan lupa ===SUARA===.
"""

# =====================================================
# TEXT TO SPEECH
# =====================================================
TTS_VOICE = os.getenv("TTS_VOICE", "id-ID-GadisNeural")
TTS_RATE = os.getenv("TTS_RATE", "-5%")


async def _edge_tts(text: str) -> bytes:
    audio = bytearray()

    async for chunk in edge_tts.Communicate(
        text,
        TTS_VOICE,
        rate=TTS_RATE,
    ).stream():
        if chunk.get("type") == "audio":
            audio.extend(chunk["data"])

    if not audio:
        raise RuntimeError("Edge TTS menghasilkan audio kosong")

    return bytes(audio)


def synthesize(text: str, lang: str = "id") -> str:
    """Menghasilkan MP3 dalam format base64."""
    text = clean_for_speech(text)

    if not text:
        raise ValueError("Teks untuk TTS kosong")

    text = text[:5000]

    try:
        audio_data = asyncio.run(_edge_tts(text))
    except Exception:
        app.logger.exception("Edge TTS gagal; mencoba gTTS")

        buffer = io.BytesIO()
        gTTS(text=text, lang=lang).write_to_fp(buffer)
        audio_data = buffer.getvalue()

    return base64.b64encode(audio_data).decode("utf-8")


# =====================================================
# HEALTH CHECK
# =====================================================
@app.get("/")
def home():
    return jsonify({
        "status": "ok",
        "message": "AI Chat API is running",
    })


@app.get("/health")
def health():
    return jsonify({
        "status": "healthy",
        "providers": list(clients.keys()),
        "model_count": len(MODELS),
    }), 200


# =====================================================
# DAFTAR MODEL
# =====================================================
@app.get("/api/models")
def list_models():
    return jsonify({
        "models": MODELS,
        "default": DEFAULT_MODEL,
    })


# =====================================================
# CHAT
# =====================================================
@app.post("/api/chat")
def chat():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Request harus berupa JSON"}), 400

    messages = data.get("messages")
    model = data.get("model") or DEFAULT_MODEL

    if not MODEL_IDS:
        return jsonify({
            "error": "Provider belum aktif. Periksa API key di Render."
        }), 503

    if not isinstance(model, str) or model not in MODEL_IDS:
        return jsonify({"error": "Model tidak dikenal atau tidak aktif"}), 400

    if not isinstance(messages, list) or not messages:
        return jsonify({"error": "Pesan tidak boleh kosong"}), 400

    if len(messages) > 100:
        return jsonify({"error": "Terlalu banyak pesan"}), 400

    validated_messages = []

    for message in messages:
        if not isinstance(message, dict):
            return jsonify({"error": "Format pesan tidak valid"}), 400

        role = message.get("role")
        content = message.get("content")

        if role not in ("user", "assistant"):
            return jsonify({"error": "Role pesan tidak valid"}), 400

        if not isinstance(content, str) or not content.strip():
            return jsonify({"error": "Isi pesan tidak valid"}), 400

        validated_messages.append({
            "role": role,
            "content": content,
        })

    if validated_messages[-1]["role"] != "user":
        return jsonify({
            "error": "Pesan terakhir harus dari user"
        }), 400

    try:
        response = clients[
            MODEL_PROVIDER[model]
        ].chat.completions.create(
            model=model,
            max_tokens=2048,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                *validated_messages,
            ],
        )

        raw = (response.choices[0].message.content or "").strip()

        if not raw:
            return jsonify({"error": "AI memberikan jawaban kosong"}), 502

    except Exception:
        app.logger.exception("Pemanggilan AI gagal")
        return jsonify({
            "error": "Gagal memanggil AI. Periksa model, API key, kuota, dan log Render."
        }), 502

    try:
        display, speech = split_reply(raw)
        speech = speech or speech_from_display(display)
    except Exception:
        app.logger.exception("Gagal memproses jawaban AI")
        display = raw
        speech = speech_from_display(raw)

    audio = None

    try:
        audio = synthesize(speech)
    except Exception:
        # Kegagalan TTS tidak menggagalkan jawaban teks.
        app.logger.exception("TTS gagal")

    return jsonify({
        "reply": display,
        "speech": speech,
        "audio": audio,
        "model": model,
    })


# =====================================================
# TTS ULANG
# =====================================================
@app.post("/api/tts")
def tts():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Request harus berupa JSON"}), 400

    text = data.get("text", "")

    if not isinstance(text, str) or not text.strip():
        return jsonify({"error": "Teks kosong"}), 400

    if len(text) > 5000:
        return jsonify({"error": "Teks maksimal 5000 karakter"}), 400

    try:
        return jsonify({"audio": synthesize(text)})
    except Exception:
        app.logger.exception("Pembuatan TTS gagal")
        return jsonify({"error": "TTS gagal. Silakan coba lagi."}), 502


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"

    app.run(
        host="0.0.0.0",
        port=port,
        debug=debug,
    )
