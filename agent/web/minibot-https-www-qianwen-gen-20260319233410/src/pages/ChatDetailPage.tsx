import React, { useState, useEffect, useRef, useCallback } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchSession, patchSessionTitle } from "../lib/api";
import { toApiMessages, streamAssistantReply, type UiMsg } from "../lib/chatStreamClient";

const ChatDetailPage: React.FC = () => {
  const { id: sessionId } = useParams<{ id: string }>();
  const [messages, setMessages] = useState<UiMsg[]>([]);
  const [title, setTitle] = useState("");
  const [updatedAt, setUpdatedAt] = useState("");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [inputValue, setInputValue] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [model, setModel] = useState("qwen-plus");
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const titleInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    if (!sessionId) return;
    setLoadError(null);
    try {
      const data = await fetchSession(sessionId);
      setTitle(data.title);
      setUpdatedAt(data.updated_at);
      setMessages(
        (data.messages || []).map((m, i) => ({
          id: `m-${i}-${m.role}`,
          role: m.role,
          content: m.content,
        })),
      );
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : "載入失敗");
    }
  }, [sessionId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isSubmitting]);

  useEffect(() => {
    if (isEditingTitle && titleInputRef.current) {
      titleInputRef.current.focus();
      titleInputRef.current.select();
    }
  }, [isEditingTitle]);

  const handleTitleSave = async () => {
    if (!sessionId || !newTitle.trim()) return;
    try {
      const r = await patchSessionTitle(sessionId, newTitle.trim());
      setTitle(r.title);
      setIsEditingTitle(false);
    } catch (e) {
      console.error(e);
      setNewTitle(title);
      setIsEditingTitle(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const text = inputValue.trim();
    if (!text || !sessionId || isSubmitting) return;

    const userMsg: UiMsg = { id: `u-${Date.now()}`, role: "user", content: text };
    setInputValue("");
    setMessages((prev) => [...prev, userMsg]);
    setIsSubmitting(true);

    const apiMessages = [...toApiMessages(messages), { role: "user" as const, content: text }];
    const asstId = `a-${Date.now()}`;
    setMessages((prev) => [...prev, { id: asstId, role: "assistant", content: "" }]);

    let accumulated = "";

    await streamAssistantReply(apiMessages, {
      sessionId,
      model,
      onDelta: (delta) => {
        accumulated += delta;
        setMessages((prev) => {
          const next = [...prev];
          const last = next[next.length - 1];
          if (last?.role === "assistant") {
            next[next.length - 1] = { ...last, content: accumulated };
          }
          return next;
        });
      },
      onError: (msg) => {
        setMessages((prev) => {
          const next = [...prev];
          const last = next[next.length - 1];
          if (last?.role === "assistant" && !last.content) {
            next[next.length - 1] = { ...last, content: `❌ ${msg}` };
          } else {
            next.push({ id: `e-${Date.now()}`, role: "assistant", content: `❌ ${msg}` });
          }
          return next;
        });
      },
    });

    setIsSubmitting(false);
    await load();
  };

  if (!sessionId) {
    return (
      <div className="p-8 text-center text-slate-600">
        無效的對話 ID
        <Link to="/chat" className="block mt-4 text-blue-600">
          新開對話
        </Link>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="p-8 text-center">
        <p className="text-red-600">{loadError}</p>
        <button type="button" onClick={() => load()} className="mt-4 text-blue-600 underline">
          重試
        </button>
        <Link to="/history" className="block mt-2 text-slate-600">
          返回歷史
        </Link>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <header className="border-b border-slate-200 bg-white px-4 py-4">
        <div className="max-w-3xl mx-auto flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            {isEditingTitle ? (
              <input
                ref={titleInputRef}
                type="text"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void handleTitleSave();
                  if (e.key === "Escape") {
                    setIsEditingTitle(false);
                    setNewTitle(title);
                  }
                }}
                onBlur={() => void handleTitleSave()}
                className="text-xl font-bold border-b-2 border-blue-500 bg-transparent w-full max-w-md focus:outline-none"
              />
            ) : (
              <h1
                className="text-xl font-bold text-slate-900 cursor-pointer hover:text-blue-600"
                onClick={() => {
                  setNewTitle(title);
                  setIsEditingTitle(true);
                }}
                title="點擊編輯標題"
              >
                {title || "對話"}
              </h1>
            )}
            <p className="text-xs text-slate-500 mt-1">{updatedAt}</p>
          </div>
          <div className="flex items-center gap-3 flex-wrap">
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="text-sm border border-slate-300 rounded-lg px-2 py-1.5 bg-white"
              disabled={isSubmitting}
            >
              <option value="qwen-plus">qwen-plus</option>
              <option value="qwen-max">qwen-max</option>
              <option value="qwen-turbo">qwen-turbo</option>
            </select>
            <Link to="/chat" className="text-sm text-blue-600">
              新對話
            </Link>
            <Link to="/history" className="text-sm text-blue-600">
              歷史
            </Link>
            <Link to="/" className="text-sm text-slate-600">
              首頁
            </Link>
          </div>
        </div>
      </header>

      <main className="flex-1 container mx-auto px-4 py-6 max-w-3xl w-full flex flex-col min-h-0">
        <div className="flex-1 flex flex-col bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden min-h-[50vh]">
          <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-slate-50/80">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                    msg.role === "user"
                      ? "bg-blue-600 text-white rounded-br-md"
                      : "bg-white border border-slate-200 text-slate-800 rounded-bl-md shadow-sm"
                  }`}
                >
                  {msg.content || (msg.role === "assistant" && isSubmitting ? "…" : "")}
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          <form onSubmit={handleSubmit} className="border-t border-slate-200 p-3 bg-white flex gap-2">
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="繼續對話…"
              className="flex-1 rounded-xl border border-slate-300 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={isSubmitting}
            />
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-5 py-2.5 rounded-xl bg-blue-600 text-white text-sm font-medium disabled:opacity-50"
            >
              送出
            </button>
          </form>
        </div>
      </main>
    </div>
  );
};

export default ChatDetailPage;
