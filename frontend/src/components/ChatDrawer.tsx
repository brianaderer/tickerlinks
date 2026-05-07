import { useState, useRef, useEffect } from "react";
import { useAppStore } from "../store";
import type { ChatMessage } from "../store";
import { HiOutlineXMark, HiOutlinePaperAirplane } from "react-icons/hi2";

const STUB_RESPONSES = [
  "AAPL is showing a bullish convergence right now -- RSI reversal plus a sentiment surge from positive services revenue coverage. Confidence is at 82%.",
  "Looking at the signal weights, the RSI Oversold detector has the highest accuracy at 72% across 340 samples. It's been reliable.",
  "GOOGL is under pressure. Negative sentiment from the EU antitrust probe is dragging the score to -0.35. Two bearish signals active.",
  "The latest hourly report flagged 6 new signal matches -- 4 bullish, 2 bearish. AAPL and MSFT are driving most of the activity.",
  "JPM had a MACD crossover detected at 65% confidence. Modest signal, but the dividend news adds a positive fundamental backdrop.",
  "Across the watchlist, sentiment is net positive. Only GOOGL and XOM are in negative territory right now.",
];

let stubIndex = 0;

function getStubResponse(): string {
  const response = STUB_RESPONSES[stubIndex % STUB_RESPONSES.length];
  stubIndex++;
  return response;
}

export default function ChatDrawer() {
  const chatOpen = useAppStore((s) => s.chatOpen);
  const setChatOpen = useAppStore((s) => s.setChatOpen);
  const messages = useAppStore((s) => s.chatMessages);
  const addMessage = useAppStore((s) => s.addChatMessage);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  function handleSend() {
    const text = input.trim();
    if (!text) return;

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
      timestamp: new Date(),
    };
    addMessage(userMsg);
    setInput("");
    setIsTyping(true);

    // Stub: simulate a response after a short delay
    setTimeout(() => {
      const reply: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: getStubResponse(),
        timestamp: new Date(),
      };
      addMessage(reply);
      setIsTyping(false);
    }, 800 + Math.random() * 600);
  }

  return (
    <>
      {/* Backdrop */}
      {chatOpen && (
        <div
          className="fixed inset-0 z-40 bg-stone-900/20 backdrop-blur-sm transition-opacity"
          onClick={() => setChatOpen(false)}
        />
      )}

      {/* Drawer */}
      <div
        className={`fixed top-0 right-0 z-50 h-screen w-full max-w-md bg-stone-50 border-l border-stone-300 shadow-2xl transition-transform duration-300 ${
          chatOpen ? "translate-x-0" : "translate-x-full"
        } flex flex-col`}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 h-14 border-b border-stone-200">
          <div className="flex items-center gap-2">
            <span className="font-serif font-black text-lg text-stone-900">Linky</span>
            <span className="text-xs font-sans text-stone-400">Market Intelligence</span>
          </div>
          <button
            onClick={() => setChatOpen(false)}
            className="text-stone-400 hover:text-stone-700"
          >
            <HiOutlineXMark className="w-5 h-5" />
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[85%] px-4 py-2.5 rounded-xl text-sm leading-relaxed ${
                  msg.role === "user"
                    ? "bg-stone-900 text-stone-50 font-sans"
                    : "bg-white border border-stone-200 text-stone-700 font-body shadow-sm"
                }`}
              >
                {msg.content}
              </div>
            </div>
          ))}
          {isTyping && (
            <div className="flex justify-start">
              <div className="bg-white border border-stone-200 rounded-xl px-4 py-2.5 shadow-sm">
                <span className="text-sm text-stone-400 font-sans animate-pulse">Linky is thinking...</span>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="border-t border-stone-200 px-5 py-3">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
            className="flex items-center gap-2"
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask Linky anything..."
              className="flex-1 bg-white border border-stone-200 text-stone-700 text-sm font-sans rounded-lg px-4 py-2.5 focus:outline-none focus:ring-1 focus:ring-stone-400"
            />
            <button
              type="submit"
              disabled={!input.trim()}
              className="p-2.5 bg-stone-900 text-stone-50 rounded-lg hover:bg-stone-800 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <HiOutlinePaperAirplane className="w-4 h-4" />
            </button>
          </form>
        </div>
      </div>
    </>
  );
}
