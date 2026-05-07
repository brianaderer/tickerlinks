import { useParams, Link, useRouter } from "@tanstack/react-router";
import { useArticle } from "../api/articles";
import EmptyState from "../components/EmptyState";
import { HiOutlineArrowLeft } from "react-icons/hi2";
import { decodeHtml } from "../utils";

export default function ArticleReader() {
  const { articleId } = useParams({ strict: false });
  const router = useRouter();
  const id = Number(articleId);
  const { data: article, isLoading, isError } = useArticle(id);

  if (isLoading) {
    return (
      <div className="flex items-center gap-3 py-12 justify-center">
        <div className="w-4 h-4 border-2 border-stone-300 border-t-stone-700 rounded-full animate-spin" />
        <span className="text-sm font-sans text-stone-400">Loading article...</span>
      </div>
    );
  }
  if (isError || !article) return <EmptyState message="Article not found." />;

  const paragraphs = article.full_text
    ? article.full_text.split(/\n\n+/).filter((p) => p.trim().length > 0)
    : null;

  return (
    <article className="max-w-3xl mx-auto">
      {/* Back button */}
      <button
        onClick={() => router.history.back()}
        className="flex items-center gap-1.5 text-sm font-sans text-stone-500 hover:text-stone-900 mb-6 transition-colors"
      >
        <HiOutlineArrowLeft className="w-4 h-4" />
        <span>Back</span>
      </button>

      {/* Header */}
      <header className="border-b-2 border-stone-900 pb-4 mb-6">
        <h1 className="font-serif text-3xl font-black text-stone-900 leading-tight">{decodeHtml(article.title)}</h1>
        <div className="flex flex-wrap items-center gap-3 mt-3 text-sm font-sans text-stone-400">
          <span className="font-medium text-stone-600">{article.source_name}</span>
          {article.author && <span>by {article.author}</span>}
          {article.published_at && (
            <span>{new Date(article.published_at).toLocaleString()}</span>
          )}
        </div>

        {/* Company tags */}
        {article.companies?.length > 0 && (
          <div className="flex gap-1.5 mt-3 flex-wrap">
            {article.companies.map((c) => (
              <Link
                key={c.symbol}
                to="/companies/$symbol"
                params={{ symbol: c.symbol }}
                className={`inline-flex items-center px-2.5 py-1 text-xs font-sans font-semibold border rounded hover:opacity-80 transition-colors ${
                  c.sentiment === "bullish" ? "bg-emerald-50 text-emerald-800 border-emerald-200" :
                  c.sentiment === "bearish" ? "bg-red-50 text-red-800 border-red-200" :
                  "bg-stone-100 text-stone-700 border-stone-200"
                }`}
              >
                {c.symbol}
              </Link>
            ))}
          </div>
        )}
      </header>

      {article.content_source === "summary" && (
        <div className="flex items-center gap-2 px-3 py-2 mb-6 bg-amber-50 border border-amber-200 rounded-lg">
          <span className="text-xs font-sans font-semibold text-amber-700 uppercase tracking-wide">Summary only</span>
          <span className="text-xs font-sans text-amber-600">Full article text could not be retrieved from the source.</span>
        </div>
      )}

      {article.content_source === "scraped" && article.summary && (
        <p className="font-body text-base text-stone-600 leading-relaxed italic border-l-2 border-stone-200 pl-3 mb-8">{decodeHtml(article.summary)}</p>
      )}

      {paragraphs ? (
        <div className="space-y-4">
          {paragraphs.map((p, i) => (
            <p key={i} className="font-body text-base text-stone-800 leading-relaxed">{decodeHtml(p)}</p>
          ))}
        </div>
      ) : (
        <div className="border-t border-stone-200 pt-6">
          <p className="font-sans text-sm text-stone-400 italic mb-4">
            Full text not available for this article.
          </p>
          <a
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            className="font-sans text-sm font-medium text-stone-900 underline underline-offset-2 decoration-stone-300 hover:decoration-stone-900"
          >
            Read on {article.source_name} &rarr;
          </a>
        </div>
      )}

      {/* Source link footer */}
      {paragraphs && (
        <div className="border-t border-stone-200 mt-8 pt-4">
          <a
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            className="font-sans text-sm text-stone-400 hover:text-stone-700 underline underline-offset-2 decoration-stone-300 hover:decoration-stone-700"
          >
            Original source: {article.source_name} &rarr;
          </a>
        </div>
      )}
    </article>
  );
}
