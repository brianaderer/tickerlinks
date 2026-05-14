import { useState, useRef, useEffect } from "react";
import { useAppStore } from "../store";
import type { ChatMessage } from "../store";
import { API_URL } from "../api/client";
import { HiOutlineXMark, HiOutlinePaperAirplane } from "react-icons/hi2";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

function normalizeChatMarkdown(raw: string) {
  let text = raw || "";
  text = text.replace(
    /(\|[^\n]+?\|)\s*(\|[-:\s|]{3,}\|)\s*(\|[^\n]+?\|)/g,
    "$1\n$2\n$3",
  );
  text = text.replace(/\|\|\s*(?=\|?[$A-Za-z0-9])/g, "|\n|");
  return text;
}

const markdownComponents: Components = {
  table: ({ children }) => (
    <div className="my-2 overflow-x-auto">
      <table className="min-w-full border-collapse text-xs">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="border-b border-stone-300">{children}</thead>,
  tr: ({ children }) => <tr className="border-b border-stone-200 last:border-0">{children}</tr>,
  th: ({ children }) => <th className="px-2 py-1 text-left font-semibold">{children}</th>,
  td: ({ children }) => <td className="px-2 py-1 align-top">{children}</td>,
};

export default function ChatDrawer() {
  const chatOpen = useAppStore((s) => s.chatOpen);
  const setChatOpen = useAppStore((s) => s.setChatOpen);
  const messages = useAppStore((s) => s.chatMessages);
  const addMessage = useAppStore((s) => s.addChatMessage);
  const pageContext = useAppStore((s) => s.pageContext);
  const toolStatus = useAppStore((s) => s.chatToolStatus);
  const setChatStreaming = useAppStore((s) => s.setChatStreaming);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  async function handleSend() {
    const text = input.trim();
    if (!text || isTyping) return;

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
      timestamp: new Date(),
    };
    addMessage(userMsg);
    setInput("");
    setIsTyping(true);
    setChatStreaming(true);

    const history = [...messages, userMsg].map((m) => ({
      role: m.role,
      content: m.content,
    }));

    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: history,
          page_context: pageContext,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: "Request failed" }));
        throw new Error(err.error || `HTTP ${res.status}`);
      }

      const data = await res.json();
      const reply: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: data.response || "No response.",
        timestamp: new Date(),
      };
      addMessage(reply);
    } catch (err) {
      const reply: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: `Sorry, I hit an error: ${err instanceof Error ? err.message : "Unknown error"}`,
        timestamp: new Date(),
      };
      addMessage(reply);
    } finally {
      setIsTyping(false);
      setChatStreaming(false);
    }
  }

  return (
    <>
      {chatOpen && (
        <div
          className="fixed inset-0 z-40 bg-stone-900/20 backdrop-blur-sm transition-opacity"
          onClick={() => setChatOpen(false)}
        />
      )}

      <div
        className={`fixed top-0 right-0 z-50 h-screen w-full lg:w-2/3 bg-stone-50 border-l border-stone-300 shadow-2xl transition-transform duration-300 ${
          chatOpen ? "translate-x-0" : "translate-x-full"
        } flex flex-col`}
      >
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
                    : "bg-white border border-stone-200 text-stone-700 shadow-sm"
                }`}
              >
                {msg.role === "assistant" ? (
                  <div className="font-body prose prose-stone prose-sm max-w-none">
                    <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                      {normalizeChatMarkdown(msg.content)}
                    </ReactMarkdown>
                  </div>
                ) : (
                  msg.content
                )}
              </div>
            </div>
          ))}
          {isTyping && (
            <div className="flex justify-start">
              <div className="bg-white border border-stone-200 rounded-xl px-4 py-2.5 shadow-sm">
                <span className="text-sm text-stone-400 font-sans animate-pulse">
                  {toolStatus ? `Looking up ${toolStatus}...` : "Linky is thinking..."}
                </span>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

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
              disabled={!input.trim() || isTyping}
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
