import React, { useState, useEffect, useRef } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toApiMessages, streamAssistantReply, type UiMsg } from "../lib/chatStreamClient";

const ChatPage: React.FC = () => {
  const navigate = useNavigate();
  const [messages, setMessages] = useState<UiMsg[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [model, setModel] = useState("qwen-plus");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isSubmitting]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const text = inputValue.trim();
    if (!text || isSubmitting) return;

    const userMsg: UiMsg = {
      id: `u-${Date.now()}`,
      role: "user",
      content: text,
    };
    setInputValue("");
    setMessages((prev) => [...prev, userMsg]);
    setIsSubmitting(true);

    const apiMessages = [...toApiMessages(messages), { role: "user" as const, content: text }];

    const asstId = `a-${Date.now()}`;
    setMessages((prev) => [...prev, { id: asstId, role: "assistant", content: "" }]);

    let accumulated = "";

    const { sessionId: newSid, fatalError } = await streamAssistantReply(apiMessages, {
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

    if (!fatalError && newSid) {
      navigate(`/chat/${newSid}`, { replace: true });
    }

    setIsSubmitting(false);
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <header className="border-b border-slate-200 bg-white px-4 py-4 flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900">MiniBot 對話</h1>
          <p className="text-sm text-slate-500">需先啟動後端（start-backend.bat）</p>
        </div>
        <div className="flex items-center gap-3 flex-wrap justify-end">
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
          <Link to="/" className="text-sm text-blue-600 hover:underline">
            首頁
          </Link>
          <Link to="/history" className="text-sm text-blue-600 hover:underline">
            歷史
          </Link>
        </div>
      </header>

      <main className="flex-1 container mx-auto px-4 py-6 max-w-3xl w-full flex flex-col min-h-0">
        <div className="flex-1 flex flex-col bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden min-h-[50vh]">
          <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-slate-50/80">
            {messages.length === 0 ? (
              <div className="text-center py-16 text-slate-500 text-sm">
                <p>輸入訊息開始對話。</p>
                <p className="mt-2">送出後會建立 session 並跳轉到專屬網址。</p>
              </div>
            ) : (
              messages.map((msg) => (
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
              ))
            )}
            <div ref={messagesEndRef} />
          </div>

          <form onSubmit={handleSubmit} className="border-t border-slate-200 p-3 bg-white flex gap-2">
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="輸入訊息…"
              className="flex-1 rounded-xl border border-slate-300 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={isSubmitting}
            />
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-5 py-2.5 rounded-xl bg-blue-600 text-white text-sm font-medium disabled:opacity-50 hover:bg-blue-700"
            >
              送出
            </button>
          </form>
        </div>
      </main>
    </div>
  );
};

export default ChatPage;
