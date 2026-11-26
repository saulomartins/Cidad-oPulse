export function normalizeExternalUrl(rawUrl?: string | null): string | null {
  const cleaned = (rawUrl || "").trim();
  if (!cleaned) return null;
  if (/^https?:\/\//i.test(cleaned)) return cleaned;
  if (/^[a-z0-9.-]+\.[a-z]{2,}/i.test(cleaned)) return `https://${cleaned}`;
  return null;
}

export function getDisplayHost(rawUrl?: string | null): string {
  const normalized = normalizeExternalUrl(rawUrl);
  if (!normalized) return "";
  try {
    return new URL(normalized).hostname.replace(/^www\./, "");
  } catch {
    return normalized;
  }
}

export function buildFallbackSearchUrl(query: string): string {
  return `https://www.google.com/search?q=${encodeURIComponent(query.trim())}`;
}
