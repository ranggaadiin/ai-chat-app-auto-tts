# Deploy: Render (backend) + Vercel (frontend)

Urutannya penting: backend dulu, baru frontend, lalu balik ke backend isi CORS.

## 1. Push ke GitHub
```bash
cd ai-chat
git init && git add . && git commit -m "init ai chat"
git branch -M main
git remote add origin https://github.com/<username>/ai-chat.git
git push -u origin main
```
`.env` sudah di `.gitignore`, jadi API key aman.

## 2. Backend di Render
1. render.com -> New -> Blueprint -> pilih repo (otomatis baca `render.yaml`).
   Atau manual: New Web Service, Root Directory `backend`, Build `pip install -r requirements.txt`, Start `gunicorn app:app --bind 0.0.0.0:$PORT --timeout 120`.
2. Isi env var `GROQ_API_KEY` (gratis di console.groq.com/keys) dan/atau `GEMINI_API_KEY` (gratis di aistudio.google.com/apikey). Salah satu cukup, model dari provider yang key-nya kosong otomatis nggak muncul.
3. Setelah live, catat URL-nya, mis. `https://ai-chat-backend.onrender.com`.
4. Tes: buka `<url>/api/models`, harus keluar JSON.

## 3. Frontend di Vercel
1. vercel.com -> Add New Project -> pilih repo.
2. Root Directory: `frontend` (Framework otomatis kedeteksi Vite).
3. Environment Variable: `VITE_API_URL` = URL Render dari langkah 2 (tanpa slash di akhir).
4. Deploy, catat URL Vercel-nya.

## 4. Kunci CORS
Balik ke Render -> Environment -> isi `ALLOWED_ORIGINS` = URL Vercel
(mis. `https://ai-chat.vercel.app`) -> save, service restart otomatis.

## Catatan
- Free tier Render tidur setelah idle, request pertama bisa lambat 30-60 detik.
- Jangan set `VITE_API_URL` lewat file `.env` yang di-commit; isi dari dashboard Vercel.
- Groq free tier ada limit harian per model. Kalau URL publik, pertimbangkan rate limit (mis. Flask-Limiter) biar kuota nggak habis diakses orang lain.
