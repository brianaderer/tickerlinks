const textarea = document.createElement("textarea");

export function decodeHtml(html: string): string {
  textarea.innerHTML = html;
  return textarea.value;
}
