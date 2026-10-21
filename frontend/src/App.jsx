import { useCallback, useEffect, useRef, useState } from "react";

// Kosong saat dev (pakai proxy Vite), diisi URL Render saat production
const API = import.meta.env.VITE_API_URL || "";

// Render teks jawaban: blok kode ``` jadi <pre>, `inline` jadi <code>
function RichText({ text }) {
  const parts = text.split(/```([\w+#-]*)[ \t]*\n?([\s\S]*?)```/g);
  const out = [];
  for (let i = 0; i < parts.length; i += 3) {
    if (parts[i].trim()) out.push(<InlineText key={i} text={parts[i]} />);
    if (i + 2 < parts.length) {
      out.push(
        <pre key={`c${i}`} className="code">
          {parts[i + 1] && <span className="lang">{parts[i + 1]}</span>}
          <code>{parts[i + 2].replace(/\n$/, "")}</code>
        </pre>
      );
    }
  }
  return <>{out}</>;
}

function InlineText({ text }) {
  return (
    <p>
      {text
        .trim()
        .split(/(`[^`\n]+`)/g)
        .map((s, i) =>
          s.startsWith("`") && s.endsWith("`") && s.length > 2 ? (
            <code key={i} className="inline">{s.slice(1, -1)}</code>
          ) : (
            s
          )
        )}
    </p>
  );
}

export default function App() {
  const [models, setModels] = useState([]);
  const [model, setModel] = useState("");
  const [messages, setMessages] = useState([]); // {role, content, audio?}
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [playingIdx, setPlayingIdx] = useState(null);
  const [autoPlay, setAutoPlay] = useState(true);
  const [error, setError] = useState("");

  const audioRef = useRef(null);
  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  // Langsung fokus ke kolom ketik pas web dibuka
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Ambil daftar model dari backend
  useEffect(() => {
    fetch(`${API}/api/models`)
      .then((r) => r.json())
      .then((d) => {
        setModels(d.models);
        setModel(d.default);
      })
      .catch(() => setError("Backend belum jalan (cek Flask di port 5000)"));
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const stopAudio = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    setPlayingIdx(null);
  }, []);

  const playAudio = useCallback(
    async (idx, msgs) => {
      stopAudio();
      const msg = msgs[idx];
      if (!msg) return;

      let audio = msg.audio;
      // Kalau audio belum ada (TTS sempat gagal), minta ulang ke backend
      if (!audio) {
        try {
          const res = await fetch(`${API}/api/tts`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: msg.speech || msg.content }),
          });
          const data = await res.json();
          if (!res.ok) throw new Error(data.error);
          audio = data.audio;
          setMessages((prev) =>
            prev.map((m, i) => (i === idx ? { ...m, audio } : m))
          );
        } catch (e) {
          setError(e.message || "Gagal bikin suara");
          return;
        }
      }

      const el = new Audio(`data:audio/mp3;base64,${audio}`);
      audioRef.current = el;
      el.onended = () => setPlayingIdx(null);
      el.onerror = () => setPlayingIdx(null);
      setPlayingIdx(idx);
      el.play().catch(() => setPlayingIdx(null));
    },
    [stopAudio]
  );

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || loading || !model) return;

    stopAudio();
    setError("");
    setInput("");

    const history = [...messages, { role: "user", content: text }];
    setMessages(history);
    setLoading(true);

    try {
      const res = await fetch(`${API}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model,
          messages: history.map(({ role, content }) => ({ role, content })),
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Request gagal");

      const next = [
        ...history,
        {
          role: "assistant",
          content: data.reply,
          speech: data.speech,
          audio: data.audio,
          model: data.model,
        },
      ];
      setMessages(next);
      if (autoPlay && data.audio) playAudio(next.length - 1, next);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  }, [input, loading, model, messages, autoPlay, playAudio, stopAudio]);

  const lastAssistantIdx = () => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === "assistant") return i;
    }
    return -1;
  };

  const cycleModel = useCallback(() => {
    if (!models.length) return;
    const i = models.findIndex((m) => m.id === model);
    setModel(models[(i + 1) % models.length].id);
  }, [models, model]);

  const replayLast = useCallback(() => {
    const i = lastAssistantIdx();
    if (i >= 0) playAudio(i, messages);
  }, [messages, playAudio]);

  // Keyboard shortcuts
  useEffect(() => {
    const onKey = (e) => {
      if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === "r") {
        e.preventDefault();
        replayLast();
      } else if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === "m") {
        e.preventDefault();
        cycleModel();
      } else if (e.key === "Escape") {
        stopAudio();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [replayLast, cycleModel, stopAudio]);

  const onInputKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  const clearChat = () => {
    stopAudio();
    setMessages([]);
    setError("");
  };

  return (
    <div className="app">
      <header className="topbar">
        <h1>AI Chat Suara</h1>
        <div className="controls">
          <select value={model} onChange={(e) => setModel(e.target.value)} title="Ganti model (Ctrl+Shift+M)">
            {models.map((m) => (
              <option key={m.id} value={m.id}>
                {m.label}
              </option>
            ))}
          </select>
          <label className="toggle" title="Putar suara otomatis">
            <input type="checkbox" checked={autoPlay} onChange={(e) => setAutoPlay(e.target.checked)} />
            Auto-play
          </label>
          <button className="ghost" onClick={replayLast} disabled={lastAssistantIdx() < 0} title="Putar ulang (Ctrl+Shift+R)">
            🔁 Ulang
          </button>
          <button className="ghost" onClick={clearChat} disabled={!messages.length}>
            🗑️ Bersihin
          </button>
        </div>
      </header>

      <main className="chat">
        {messages.length === 0 && (
          <div className="empty">
            <p>Ketik sesuatu, AI bakal jawab pakai teks dan suara.</p>
            <small>
              Shortcut: <kbd>Ctrl+Shift+R</kbd> putar ulang · <kbd>Ctrl+Shift+M</kbd> ganti model · <kbd>Esc</kbd> stop suara
            </small>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`bubble ${m.role}`}>
            {m.role === "assistant" ? <RichText text={m.content} /> : <p>{m.content}</p>}
            {m.role === "assistant" && (
              <div className="meta">
                <button
                  className="mini"
                  onClick={() => (playingIdx === i ? stopAudio() : playAudio(i, messages))}
                >
                  {playingIdx === i ? "⏹ Stop" : "🔊 Putar"}
                </button>
                {m.model && <span>{m.model}</span>}
              </div>
            )}
          </div>
        ))}

        {loading && <div className="bubble assistant typing">AI lagi mikir…</div>}
        {error && <div className="error">{error}</div>}
        <div ref={bottomRef} />
      </main>

      <footer className="composer">
        <textarea
          ref={inputRef}
          autoFocus
          rows={1}
          value={input}
          placeholder="Tanya apa aja… (Enter kirim, Shift+Enter baris baru)"
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onInputKey}
        />
        <button onClick={send} disabled={loading || !input.trim() || !model}>
          Kirim
        </button>
      </footer>
    </div>
  );
}
