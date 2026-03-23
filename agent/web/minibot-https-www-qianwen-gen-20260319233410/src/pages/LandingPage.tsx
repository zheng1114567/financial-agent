import React from "react";
import { Link } from "react-router-dom";

const LandingPage: React.FC = () => {
  return (
    <div className="min-h-screen bg-gray-900 text-white flex flex-col">
      <header className="py-8 text-center relative">
        <div className="absolute top-4 right-4 md:right-12">
          <Link to="/history" className="text-sm text-cyan-300 hover:underline">
            歷史紀錄
          </Link>
        </div>
        <h1 className="text-4xl md:text-5xl font-bold bg-gradient-to-r from-blue-400 to-cyan-300 bg-clip-text text-transparent">
          MiniBot
        </h1>
        <p className="mt-3 text-gray-300 max-w-2xl mx-auto text-lg">
          Your intelligent, fast, and secure AI customer support assistant — ready in one click.
        </p>
      </header>

      <main className="flex-1 container mx-auto px-4 py-8">
        <div className="max-w-4xl mx-auto space-y-8">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-gray-800 rounded-xl p-6 border border-gray-700 hover:border-blue-500 transition-colors">
              <h3 className="text-xl font-semibold mb-2 text-blue-300">⚡ Instant Start</h3>
              <p className="text-gray-300">No login required. Start chatting in under 2 seconds.</p>
            </div>
            <div className="bg-gray-800 rounded-xl p-6 border border-gray-700 hover:border-blue-500 transition-colors">
              <h3 className="text-xl font-semibold mb-2 text-blue-300">📚 Persistent History</h3>
              <p className="text-gray-300">All chats saved. Share URLs or browse your archive.</p>
            </div>
            <div className="bg-gray-800 rounded-xl p-6 border border-gray-700 hover:border-blue-500 transition-colors">
              <h3 className="text-xl font-semibold mb-2 text-blue-300">🔒 Zero-Trust Security</h3>
              <p className="text-gray-300">End-to-end encrypted. No data stored. GDPR-ready.</p>
            </div>
          </div>

          <div className="text-center pt-4 flex flex-col sm:flex-row gap-4 justify-center items-center">
            <Link
              to="/chat"
              className="inline-block px-8 py-4 bg-gradient-to-r from-blue-600 to-cyan-500 hover:from-blue-700 hover:to-cyan-600 text-white font-bold rounded-xl text-lg shadow-lg hover:shadow-xl transform hover:-translate-y-0.5 transition-all duration-200"
            >
              開始對話 →
            </Link>
          </div>
        </div>
      </main>

      <footer className="py-6 text-center text-gray-500 text-sm mt-12 border-t border-gray-800">
        <p>© 2026 MiniBot. Built with ❤️ and Qwen-style elegance.</p>
      </footer>
    </div>
  );
};

export default LandingPage;