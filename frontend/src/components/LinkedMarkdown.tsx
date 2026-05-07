import { Link } from "@tanstack/react-router";
import ReactMarkdown, { type Components } from "react-markdown";
import type { ReactNode } from "react";
import { useCompanies } from "../api/companies";

const TICKER_RE = /\b([A-Z]{1,5}(?:\.[A-Z]{1,2})?)\b(?!\()/g;

function linkifyText(text: string, symbols: Set<string>): ReactNode[] {
  const parts: ReactNode[] = [];
  let lastIndex = 0;

  for (const match of text.matchAll(TICKER_RE)) {
    const ticker = match[1];
    const idx = match.index!;

    if (!symbols.has(ticker)) continue;

    if (idx > lastIndex) {
      parts.push(text.slice(lastIndex, idx));
    }
    parts.push(
      <Link
        key={`${ticker}-${idx}`}
        to="/companies/$symbol"
        params={{ symbol: ticker }}
        className="font-semibold text-stone-900 underline underline-offset-2 decoration-stone-300 hover:decoration-stone-900"
      >
        {ticker}
      </Link>
    );
    lastIndex = idx + ticker.length;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts.length > 0 ? parts : [text];
}

function makeComponents(symbols: Set<string>): Components {
  function processChildren(children: ReactNode): ReactNode {
    if (typeof children === "string") {
      return <>{linkifyText(children, symbols)}</>;
    }
    if (Array.isArray(children)) {
      return <>{children.map((child, i) =>
        typeof child === "string" ? <span key={i}>{linkifyText(child, symbols)}</span> : child
      )}</>;
    }
    return children;
  }

  return {
    p: ({ children }) => <p>{processChildren(children)}</p>,
    li: ({ children }) => <li>{processChildren(children)}</li>,
    strong: ({ children }) => <strong>{processChildren(children)}</strong>,
    em: ({ children }) => <em>{processChildren(children)}</em>,
  };
}

interface Props {
  children: string;
  className?: string;
}

export default function LinkedMarkdown({ children, className }: Props) {
  const { data: companies } = useCompanies();
  const symbols = new Set(companies?.map((c) => c.symbol) || []);
  const components = makeComponents(symbols);

  return (
    <div className={className || "font-body text-sm text-stone-700 leading-relaxed prose prose-stone prose-sm max-w-none"}>
      <ReactMarkdown components={components}>{children}</ReactMarkdown>
    </div>
  );
}
