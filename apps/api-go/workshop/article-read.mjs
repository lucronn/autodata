import { delay } from "./catalog.mjs";

const sourceProbeIntervalMs = 250;
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
function articleRetryAfter(response) {
  return Math.max(
    Number(response?.retryAfterSeconds) || 0,
    Number(response?.data?.article?.processing?.retry_after_seconds) || 0,
  );
}
export async function readArticle(
  read,
  {
    signal,
    onUpdate = () => {},
    selectResponse = (response) => response,
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
  let confirmedSourceCapture = false;
  let regularSourceReadAt = 0;
  let sourceConfirmationAt = 0;
  let publicationReadAt = 0;
  let publicationProbeJob;
  let sawFastSource = false;
  let attempt = 0;
  while (now() < deadline) {
    signal?.throwIfAborted();
    let retryAfter = 0, fastPendingJob, fastSource = false, readable = false;
    let shortSourceCheck = false, sourceProbeFailed = false;
    let shortPublicationJob;
    const startedAt = now();
    if (firstReadAt <= startedAt) firstReadAt = 0;
    if (nextSourceProbeAt <= startedAt) nextSourceProbeAt = 0;
    if (regularSourceReadAt <= startedAt) regularSourceReadAt = 0;
    if (sourceConfirmationAt <= startedAt) sourceConfirmationAt = 0;
    if (publicationReadAt <= startedAt) publicationReadAt = 0;
    const readDeadline = Math.min(
      deadline, firstReadAt || deadline, nextSourceProbeAt || deadline,
      regularSourceReadAt || deadline, sourceConfirmationAt || deadline, publicationReadAt || deadline,
    );
    const firstScheduledSourceRead = !firstReadAt && confirmedSourceCapture && earlyConfirmationJob !== undefined;
    // Keep the header deadline for a short read. Give a successful body on
    // the later probes one extra interval to finish without downloading twice.
    const sourceBodyDeadline = firstReadAt
      ? firstReadAt + (nextSourceProbeAt ? 0 : sourceProbeIntervalMs)
      : regularSourceReadAt && regularSourceReadAt + sourceProbeIntervalMs;
    const bodyDeadline = sourceBodyDeadline ||
      (publicationReadAt && publicationReadAt + publicationProbeIntervalMs);
    try {
      const response = await read({
        signal,
        timeout: Math.max(1, Math.floor(Math.min(10000, readDeadline - startedAt))),
        readableBodyTimeout: bodyDeadline ? Math.floor(Math.min(deadline, bodyDeadline) - startedAt) : undefined,
        finishPublishedBody: Boolean(publicationReadAt),
        preferShortSourceCheck: Boolean(firstReadAt || regularSourceReadAt || firstScheduledSourceRead),
        preferShortPublicationCheck: !sawFastSource || Boolean(publicationReadAt),
      });
      signal?.throwIfAborted();
      latest = selectResponse(response);
      if (!latest?.data?.article || typeof latest.data.article !== "object")
        throw new Error("The article response is unreadable.");
      onUpdate(latest);
      retryAfter = articleRetryAfter(latest);
      if (response !== latest) retryAfter = Math.max(retryAfter, articleRetryAfter(response));
      const article = latest.data.article;
      if (!processingArticle(article))
        return { ...latest, timedOut: false };
      readable = readableArticle(article);
      shortSourceCheck = latest.shortSourceCheck === true && retryAfter === 0 &&
        latest.status === 202 && !readable &&
        ["queued", "fetching_source"].includes(article.processing.state);
      const readableSource = latest.status === 200 && readable && article.content_origin === "source";
      if (latest.shortPublicationCheck === true && retryAfter === 0 &&
          readableSource && ["normalizing", "rewriting", "validating", "publishing"].includes(article.processing.state)) {
        shortPublicationJob = article.processing.job_id;
      }
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
      confirmedSourceCapture = (firstSourceProbePending || confirmedSourceCapture) && samePendingSource &&
        latest.data.article.processing.state === "fetching_source";
      if (nextSourceProbeAt && retryAfter === 0 && (samePendingSource || sourceProbeFailed)) {
        const probeWait = Math.max(0, nextSourceProbeAt - now());
        // A confirmed fetch can finish before the next scheduled read. Give
        // this check the time left before that read and keep it on a miss.
        const activeCaptureWait = probeWait - sourceProbeIntervalMs / 2;
        if (!firstSourceProbePending && activeCaptureWait > 0 && samePendingSource &&
            latest.data.article.processing.state === "fetching_source") {
          firstSourceProbePending = true;
          await wait(Math.min(remaining, activeCaptureWait), signal);
          continue;
        }
        nextSourceProbeAt = 0;
        firstSourceProbePending ||= samePendingSource;
        await wait(Math.min(remaining, probeWait), signal);
        continue;
      }
      // Spend one more read only when both short probes confirmed the same capture.
      const finalProbeWait = firstReadAt - sourceProbeIntervalMs - now();
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
    if (regularSourceReadAt) {
      const regularWait = Math.max(0, regularSourceReadAt - now());
      regularSourceReadAt = 0;
      if (!readable) {
        await wait(Math.min(remaining, Math.max(regularWait, retryAfter * 1000)), signal);
        continue;
      }
    }
    if (publicationReadAt) {
      // If the first probe still sees the same active rewrite, try once
      // halfway to the ordinary read.
      const probeWait = publicationReadAt - publicationProbeIntervalMs / 2 - now();
      const samePublicationJob = publicationProbeJob && publicationProbeJob === shortPublicationJob;
      publicationProbeJob = undefined;
      if (samePublicationJob && probeWait > 0) {
        await wait(Math.min(remaining, probeWait), signal);
        continue;
      }
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
      nextSourceProbeAt = scheduledAt + 2 * sourceProbeIntervalMs;
      backoff = sourceProbeIntervalMs;
    } else if (attempt === 1 && fastPendingJob) {
      // Add an early check for newly retained source. If this check misses,
      // keep the normal two-second check before resuming the usual backoff.
      earlyConfirmationJob = fastPendingJob;
    } else if (earlyConfirmationJob !== undefined) {
      const stillFetching = firstScheduledSourceRead && shortSourceCheck &&
        latest.data.article.processing.job_id === earlyConfirmationJob &&
        latest.data.article.processing.state === "fetching_source";
      if (fastPendingJob === earlyConfirmationJob || stillFetching) {
        backoff = 1000;
        attempt--;
      }
      if (stillFetching) {
        // Keep the next ordinary read if this resumed short check misses.
        regularSourceReadAt = now() + backoff;
        backoff = sourceProbeIntervalMs;
      }
      earlyConfirmationJob = undefined;
    }
    // Check once for the rewrite shortly after stored source appears.
    // A miss rejoins the normal backoff and still honors Retry-After.
    if (sourceConfirmationAt) {
      backoff = Math.max(0, sourceConfirmationAt - now());
      sourceConfirmationAt = 0;
      attempt--;
    } else if ((fastSource || shortPublicationJob) && !sawFastSource) {
      sawFastSource = true;
      if (backoff > 1000) {
        sourceConfirmationAt = now() + backoff;
        backoff = 1000;
      }
      if (shortPublicationJob) {
        publicationReadAt = now() + backoff;
        publicationProbeJob = shortPublicationJob;
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
