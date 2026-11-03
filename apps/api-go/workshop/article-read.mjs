import { delay } from "./catalog.mjs";

export class NavigationGeneration {
  #controller;
  next() {
    this.clear();
    const controller = new AbortController();
    this.#controller = controller;
    return {
      signal: controller.signal,
      current: () =>
        this.#controller === controller && !controller.signal.aborted,
    };
  }
  clear() {
    this.#controller?.abort();
    this.#controller = null;
  }
}
export function readableArticle(article) {
  return Boolean(
    article &&
      (article.document?.blocks?.length ||
        article.steps?.some(
          (s) => s.action || s.heading || s.instructions?.length,
        ) ||
        article.body?.trim()),
  );
}
export function processingArticle(article) {
  return Boolean(
    article?.processing?.job_id &&
      !["completed", "needs_review", "failed", "withdrawn"].includes(
        article.processing.state,
      ),
  );
}
export async function readArticle(
  read,
  {
    signal,
    onUpdate = () => {},
    wait = delay,
    now = () => performance.now(),
    budgetMs = 120000,
  } = {},
) {
  const deadline = now() + Math.min(120000, Math.max(0, budgetMs));
  let latest,
    attempt = 0;
  while (now() < deadline) {
    signal?.throwIfAborted();
    let retryAfter = 0;
    try {
      latest = await read({
        signal,
        timeout: Math.min(10000, Math.max(1, deadline - now())),
      });
      signal?.throwIfAborted();
      if (!latest?.data?.article || typeof latest.data.article !== "object")
        throw new Error("The article response is unreadable.");
      onUpdate(latest);
      retryAfter = Math.max(
        Number(latest.retryAfterSeconds) || 0,
        Number(latest.data.article.processing?.retry_after_seconds) || 0,
      );
      if (!processingArticle(latest.data.article))
        return { ...latest, timedOut: false };
    } catch (error) {
      signal?.throwIfAborted();
      if (
        !(
          error instanceof TypeError ||
          error.code === "NETWORK_UNAVAILABLE" ||
          ([429, 503].includes(error.status) && error.retryable)
        )
      )
        throw error;
      retryAfter = Number(error.retryAfterSeconds) || 0;
    }
    const remaining = deadline - now();
    if (remaining <= 0) break;
    const backoff = [1000, 2000, 4000, 8000, 10000][Math.min(attempt++, 4)];
    await wait(
      Math.min(remaining, Math.max(backoff, retryAfter * 1000)),
      signal,
    );
  }
  signal?.throwIfAborted();
  return { ...latest, timedOut: true };
}
