import React, { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { fetchSessions, type SessionSummary } from "../lib/api";

const HistoryPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchTerm, setSearchTerm] = useState("");
  const [history, setHistory] = useState<SessionSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchSessions();
        if (!cancelled) setHistory(data.sessions || []);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "載入失敗");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const filtered = history.filter(
    (item) =>
      item.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (item.last_preview || "").toLowerCase().includes(searchTerm.toLowerCase()),
  );

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <header className="border-b border-slate-200 bg-white px-4 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900">對話歷史</h1>
          <p className="text-sm text-slate-500">僅顯示本機瀏覽器 X-Client-ID 下的 session</p>
        </div>
        <div className="flex gap-3 text-sm">
          <Link to="/chat" className="text-blue-600 hover:underline">
            新對話
          </Link>
          <Link to="/" className="text-slate-600 hover:underline">
            首頁
          </Link>
        </div>
      </header>

      <main className="flex-1 container mx-auto px-4 py-6 max-w-3xl w-full">
        <div className="bg-white rounded-xl border border-slate-200 p-4 mb-6 shadow-sm">
          <label className="text-sm font-medium text-slate-700 block mb-2">搜尋</label>
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="標題或預覽文字…"
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
          />
        </div>

        {loading && <p className="text-center text-slate-500 py-12">載入中…</p>}
        {error && (
          <div className="rounded-xl border border-red-200 bg-red-50 text-red-800 p-4 text-sm">
            {error}
            <p className="mt-2 text-xs">請確認已執行 start-backend.bat，且前端為 npm run dev。</p>
          </div>
        )}

        {!loading && !error && filtered.length === 0 && (
          <div className="text-center py-12 text-slate-500 text-sm">
            {history.length === 0 ? "尚無紀錄，先去開一則對話。" : "沒有符合搜尋的項目。"}
            {searchTerm ? (
              <button
                type="button"
                onClick={() => setSearchTerm("")}
                className="block mx-auto mt-4 text-blue-600 underline"
              >
                清除搜尋
              </button>
            ) : null}
          </div>
        )}

        <ul className="space-y-3">
          {filtered.map((item) => (
            <li key={item.session_id}>
              <button
                type="button"
                onClick={() => navigate(`/chat/${item.session_id}`)}
                className="w-full text-left bg-white rounded-xl border border-slate-200 p-4 shadow-sm hover:border-blue-300 hover:shadow transition"
              >
                <div className="flex justify-between gap-2 items-start">
                  <h2 className="font-medium text-slate-900">{item.title || "未命名"}</h2>
                  <span className="text-xs text-slate-400 shrink-0">{item.updated_at}</span>
                </div>
                {item.last_preview ? (
                  <p className="mt-2 text-sm text-slate-600 line-clamp-2">{item.last_preview}</p>
                ) : null}
                <p className="mt-2 text-xs text-slate-400 font-mono truncate">{item.session_id}</p>
              </button>
            </li>
          ))}
        </ul>
      </main>
    </div>
  );
};

export default HistoryPage;
