import { delay } from "./catalog.mjs";

const publicationProbeIntervalMs = 500;

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
  let firstReadAt = 0;
  let nextSourceProbeAt = 0;
  let firstSourceProbePending = false;
  let sourceConfirmationAt = 0;
  let publicationReadAt = 0;
  let sawFastSource = false;
  let attempt = 0;
  while (now() < deadline) {
    signal?.throwIfAborted();
    let retryAfter = 0, fastPendingJob, fastSource = false, readable = false;
    let shortSourceCheck = false, shortPublicationCheck = false, sourceProbeFailed = false;
    const startedAt = now();
    if (firstReadAt <= startedAt) firstReadAt = 0;
    if (nextSourceProbeAt <= startedAt) nextSourceProbeAt = 0;
    if (sourceConfirmationAt <= startedAt) sourceConfirmationAt = 0;
    if (publicationReadAt <= startedAt) publicationReadAt = 0;
    const readDeadline = Math.min(
      deadline, firstReadAt || deadline, nextSourceProbeAt || deadline,
      sourceConfirmationAt || deadline, publicationReadAt || deadline,
    );
    // Once a short read has the published view, let it finish transferring for
    // one probe interval past the normal fallback instead of downloading twice.
    const bodyDeadline = firstReadAt && nextSourceProbeAt ? firstReadAt :
      publicationReadAt ? publicationReadAt + publicationProbeIntervalMs : 0;
    try {
      latest = await read({
        signal,
        timeout: Math.max(1, Math.floor(Math.min(10000, readDeadline - startedAt))),
        readableBodyTimeout: bodyDeadline ? Math.floor(Math.min(deadline, bodyDeadline) - startedAt) : undefined,
        finishPublishedBody: Boolean(publicationReadAt),
        preferShortSourceCheck: Boolean(firstReadAt),
        preferShortPublicationCheck: !sawFastSource || Boolean(publicationReadAt),
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
      readable = readableArticle(article);
      shortSourceCheck = latest.shortSourceCheck === true && retryAfter === 0 &&
        latest.status === 202 && !readable &&
        ["queued", "fetching_source"].includes(article.processing.state);
      const readableSource = latest.status === 200 && readable && article.content_origin === "source";
      shortPublicationCheck = latest.shortPublicationCheck === true && retryAfter === 0 &&
        readableSource && ["normalizing", "rewriting", "validating", "publishing"].includes(article.processing.state);
      if (retryAfter === 1 && article.processing.state !== "failed") {
        if (latest.status === 202 && !readable) {
          fastPendingJob = article.processing.job_id;
        }
        fastSource = readableSource;
      }
    } catch (error) {
      signal?.throwIfAborted();
      sourceProbeFailed = error instanceof TypeError || error.code === "NETWORK_UNAVAILABLE";
      if (!sourceProbeFailed && !([429, 503].includes(error.status) && error.retryable)) throw error;
      retryAfter = Number(error.retryAfterSeconds) || 0;
    }
    const remaining = deadline - now();
    if (remaining <= 0) break;
    if (firstReadAt) {
      const samePendingSource = shortSourceCheck && latest.data.article.processing.job_id === earlyConfirmationJob;
      if (nextSourceProbeAt && retryAfter === 0 && (samePendingSource || sourceProbeFailed)) {
        const probeWait = Math.max(0, nextSourceProbeAt - now());
        nextSourceProbeAt = 0;
        firstSourceProbePending = samePendingSource;
        await wait(Math.min(remaining, probeWait), signal);
        continue;
      }
      // Spend one more read only when both short probes confirmed the same capture.
      const finalProbeWait = firstReadAt - 250 - now();
      if (firstSourceProbePending && finalProbeWait > 0 && samePendingSource &&
          latest.data.article.processing.state === "fetching_source") {
        firstSourceProbePending = false;
        await wait(Math.min(remaining, finalProbeWait), signal);
        continue;
      }
      const regularWait = Math.max(0, firstReadAt - now());
      firstReadAt = 0;
      nextSourceProbeAt = 0;
      firstSourceProbePending = false;
      if (!readable) {
        // An unanswered probe must leave time for the regular first read.
        await wait(Math.min(remaining, Math.max(regularWait, retryAfter * 1000)), signal);
        continue;
      }
    }
    if (publicationReadAt) {
      // A missed publication probe rejoins the original read cadence.
      const regularWait = Math.max(0, publicationReadAt - now());
      publicationReadAt = 0;
      await wait(Math.min(remaining, Math.max(regularWait, retryAfter * 1000)), signal);
      continue;
    }
    let backoff = [1000, 2000, 4000, 8000, 10000][Math.min(attempt++, 4)];
    if (attempt === 1 && shortSourceCheck) {
      earlyConfirmationJob = latest.data.article.processing.job_id;
      const scheduledAt = now();
      firstReadAt = scheduledAt + backoff;
      // An early hit can show cheap captures sooner. Keep the half-second
      // check for a source that is still pending or an early transport miss.
      nextSourceProbeAt = scheduledAt + 500;
      backoff = 250;
    } else if (attempt === 1 && fastPendingJob) {
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
    } else if ((fastSource || shortPublicationCheck) && !sawFastSource) {
      sawFastSource = true;
      if (backoff > 1000) {
        sourceConfirmationAt = now() + backoff;
        backoff = 1000;
      }
      if (shortPublicationCheck) {
        publicationReadAt = now() + backoff;
        backoff = publicationProbeIntervalMs;
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
