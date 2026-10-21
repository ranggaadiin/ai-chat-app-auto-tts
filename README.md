# AI Chat Suara (Flask + React)

Chat AI yang jawabannya teks + suara. Ada tombol putar ulang suara dan ganti model.

## Fitur
- Jawaban AI muncul sebagai teks dan otomatis dibacakan (bisa dimatiin lewat toggle Auto-play)
- Putar ulang suara per pesan, atau pesan terakhir lewat tombol Ulang
- Ganti model AI dari dropdown
- Shortcut: `Ctrl+Shift+R` putar ulang, `Ctrl+Shift+M` ganti model (siklus), `Esc` stop suara, `Enter` kirim

## Jalanin backend
```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # isi GROQ_API_KEY dan/atau GEMINI_API_KEY
python app.py                   # jalan di http://localhost:5000
```

## Jalanin frontend
```bash
cd frontend
npm install
npm run dev                     # http://localhost:5173 (proxy /api ke Flask)
```

## Endpoint
| Method | Path | Fungsi |
|---|---|---|
| GET | /api/models | daftar model + default |
| POST | /api/chat | `{model, messages}` -> `{reply, audio(base64 mp3), model}` |
| POST | /api/tts | `{text}` -> `{audio}` (buat ulang suara kalau TTS gagal) |

## Catatan
- Suara dioptimasi buat dengerin kode tanpa liat layar: model bikin dua bagian (teks layar + naskah suara, dipisah `===SUARA===`). Kode nggak dibacakan mentah, tapi dijelaskan alurnya. Kalau model nggak ngikutin format, `speech.py` otomatis bacain kode dengan nama simbol ("kurung buka", "titik koma", camelCase dipecah).
- Suara pakai Edge TTS (neural Microsoft, gratis, tanpa API key). Default `id-ID-GadisNeural` (cewek); ganti ke `id-ID-ArdiNeural` (cowok) lewat env `TTS_VOICE`, kecepatan lewat `TTS_RATE` (mis. `+10%`). Kalau Edge TTS gagal, otomatis fallback ke gTTS.
- AI-nya pakai free tier Groq (console.groq.com/keys) dan Google Gemini (aistudio.google.com/apikey). Isi salah satu atau dua-duanya di `.env`. Edit daftar model di `ALL_MODELS` pada `app.py`.
- Free tier ada batas request per hari/menit; kalau kena limit, backend balikin pesan error.
