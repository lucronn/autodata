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
  const processing = article?.processing;
  return Boolean(
    processing?.job_id &&
      !["completed", "needs_review", "withdrawn"].includes(processing.state) &&
      (processing.state !== "failed" || processing.retryable === true),
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
  let latest, earlyConfirmationJob;
  let sourceConfirmationAt = 0;
  let sawFastSource = false;
  let attempt = 0;
  while (now() < deadline) {
    signal?.throwIfAborted();
    let retryAfter = 0, fastPendingJob, fastSource = false;
    const startedAt = now();
    if (sourceConfirmationAt <= startedAt) sourceConfirmationAt = 0;
    const readDeadline = Math.min(deadline, sourceConfirmationAt || deadline);
    try {
      latest = await read({
        signal,
        timeout: Math.max(1, Math.floor(Math.min(10000, readDeadline - startedAt))),
      });
      signal?.throwIfAborted();
      if (!latest?.data?.article || typeof latest.data.article !== "object")
        throw new Error("The article response is unreadable.");
      onUpdate(latest);
      retryAfter = Math.max(
        Number(latest.retryAfterSeconds) || 0,
        Number(latest.data.article.processing?.retry_after_seconds) || 0,
      );
      const article = latest.data.article;
      if (!processingArticle(article))
        return { ...latest, timedOut: false };
      if (retryAfter === 1 && article.processing.state !== "failed") {
        const readable = readableArticle(article);
        if (latest.status === 202 && !readable) {
          fastPendingJob = article.processing.job_id;
        }
        fastSource = latest.status === 200 && readable && article.content_origin === "source";
      }
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
    let backoff = [1000, 2000, 4000, 8000, 10000][Math.min(attempt++, 4)];
    if (attempt === 1 && fastPendingJob) {
      // Add an early check for newly retained source. If this check misses,
      // keep the normal two-second check before resuming the usual backoff.
      earlyConfirmationJob = fastPendingJob;
    } else if (earlyConfirmationJob !== undefined) {
      if (fastPendingJob === earlyConfirmationJob) {
        backoff = 1000;
        attempt--;
      }
      earlyConfirmationJob = undefined;
    }
    // Check once for the rewrite shortly after stored source appears.
    // A miss rejoins the normal backoff and still honors Retry-After.
    if (sourceConfirmationAt) {
      backoff = Math.max(0, sourceConfirmationAt - now());
      sourceConfirmationAt = 0;
      attempt--;
    } else if (fastSource && !sawFastSource) {
      sawFastSource = true;
      if (backoff > 1000) {
        sourceConfirmationAt = now() + backoff;
        backoff = 1000;
      }
    }
    await wait(
      Math.min(remaining, Math.max(backoff, retryAfter * 1000)),
      signal,
    );
  }
  signal?.throwIfAborted();
  return { ...latest, timedOut: true };
}
