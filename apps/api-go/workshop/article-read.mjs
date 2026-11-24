import { delay } from "./catalog.mjs";

const sourceProbeIntervalMs = 250;
const initialSourceProbeDelayMs = 150;
const minimumSourceProbeAdvanceMs = 50;
const initialPublicationProbeDelayMs = 250;
const publicationProbeIntervalMs = 500;
const maxArticleRequestMs = 10000;
const publicationStatusProbeDelayMs = 2000;
const latePublicationProbeMinimumBackoffMs = 8000;
const publicationStates = ["normalizing", "rewriting", "validating", "publishing"];

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
function publicationAnchor(response) {
  const article = response?.data?.article;
  if (response?.publicationCheckSupported && response.status === 200 &&
      article?.content_origin === "source" && publicationStates.includes(article.processing?.state) &&
      article.id && article.source_revision_id && article.processing.job_id) {
    return { articleId: article.id, sourceRevisionId: article.source_revision_id, jobId: article.processing.job_id };
  }
}
function matchingPublicationStatus(response, anchor) {
  const status = response.data;
  if (response.publicationStatus && response.status === 200 && status?.version === "v1" &&
      status.article_id === anchor.articleId && status.job_id === anchor.jobId &&
      status.source_revision_id === anchor.sourceRevisionId && publicationStates.includes(status.state)) {
    return status;
  }
}
export async function readArticle(
  read,
  {
    signal,
    onUpdate = () => {},
    selectResponse = (response) => response,
    wait = delay,
    now = () => performance.now(),
    initialReadStartedAt,
    budgetMs = 120000,
  } = {},
) {
  const deadline = now() + Math.min(120000, Math.max(0, budgetMs));
  let latest, earlyConfirmationJob;
  let firstReadAt = 0;
  let initialSourceFallbackAt = 0;
  let advancedSourceProbeUntil = 0;
  let nextSourceProbeAt = 0;
  let firstSourceProbePending = false;
  let confirmedSourceCapture = false;
  let regularSourceReadAt = 0;
  let sourceConfirmationAt = 0;
  let publicationReadAt = 0;
  let publicationProbeJob;
  let scheduledPublicationCheck;
  const publicationStatusProbes = new Map();
  let sawFastSource = false;
  let attempt = 0;
  while (now() < deadline) {
    signal?.throwIfAborted();
    let retryAfter = 0, fastPendingJob, fastSource = false, readable = false;
    let shortSourceCheck = false, sourceProbeFailed = false;
    let shortPublicationJob;
    const startedAt = now();
    const advancedProbeLimit = advancedSourceProbeUntil > startedAt ? advancedSourceProbeUntil : 0;
    advancedSourceProbeUntil = 0;
    const initialSourceFallback = initialSourceFallbackAt > startedAt ? initialSourceFallbackAt : 0;
    initialSourceFallbackAt = 0;
    const statusProbe = scheduledPublicationCheck?.regularReadAt > startedAt ? scheduledPublicationCheck : undefined;
    scheduledPublicationCheck = undefined;
    if (firstReadAt <= startedAt) firstReadAt = 0;
    if (nextSourceProbeAt <= startedAt) nextSourceProbeAt = 0;
    if (regularSourceReadAt <= startedAt) regularSourceReadAt = 0;
    if (sourceConfirmationAt <= startedAt) sourceConfirmationAt = 0;
    if (publicationReadAt <= startedAt) publicationReadAt = 0;
    const publicationCheck = statusProbe?.anchor ??
      (publicationReadAt || sourceConfirmationAt ? publicationAnchor(latest) : undefined);
    const finishPublishedBody = Boolean(publicationReadAt || publicationCheck);
    const readDeadline = Math.min(
      deadline, firstReadAt || deadline, nextSourceProbeAt || deadline,
      regularSourceReadAt || deadline, sourceConfirmationAt || deadline, publicationReadAt || deadline,
      statusProbe ? Math.min(statusProbe.regularReadAt, startedAt + publicationStatusProbeDelayMs) : deadline,
      initialSourceFallback || deadline, advancedProbeLimit || deadline,
    );
    const firstScheduledSourceRead = !firstReadAt && confirmedSourceCapture && earlyConfirmationJob !== undefined;
    // Keep the header deadline for a short read. Give a successful body on
    // the later probes one extra interval to finish without downloading twice.
    const sourceBodyDeadline = firstReadAt
      ? firstReadAt + (nextSourceProbeAt ? 0 : sourceProbeIntervalMs)
      : regularSourceReadAt && regularSourceReadAt + sourceProbeIntervalMs;
    // A confirmed publication can use the ordinary body deadline even
    // when the probe had a short deadline for its headers.
    const finishBodyBy = statusProbe?.late ? statusProbe.regularReadAt : startedAt + maxArticleRequestMs;
    const bodyDeadline = advancedProbeLimit || sourceBodyDeadline || (finishPublishedBody && finishBodyBy);
    try {
      const response = await read({
        signal,
        timeout: Math.max(1, Math.floor(Math.min(maxArticleRequestMs, readDeadline - startedAt))),
        readableBodyTimeout: bodyDeadline ? Math.floor(Math.min(deadline, bodyDeadline) - startedAt) : undefined,
        finishPublishedBody,
        preferShortSourceCheck: Boolean(firstReadAt || regularSourceReadAt || firstScheduledSourceRead),
        preferShortPublicationCheck: !sawFastSource || Boolean(publicationReadAt),
        publicationCheck,
      });
      signal?.throwIfAborted();
      if (publicationCheck && (response.publicationStatus || !response.data?.article)) {
        const pending = matchingPublicationStatus(response, publicationCheck);
        retryAfter = Math.max(articleRetryAfter(response), Number(pending?.retry_after_seconds) || 0);
        if (pending) {
          if (retryAfter === 0) shortPublicationJob = pending.job_id;
          const scheduled = statusProbe && publicationStatusProbes.get(pending.job_id);
          if (scheduled?.attempts === 1 && retryAfter <= publicationStatusProbeDelayMs / 1000) {
            scheduled.confirmedPending = true;
          }
        }
      } else {
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
            readableSource && publicationStates.includes(article.processing.state)) {
          shortPublicationJob = article.processing.job_id;
        }
        if (retryAfter === 1 && article.processing.state !== "failed") {
          if (latest.status === 202 && !readable) {
            fastPendingJob = article.processing.job_id;
          }
          fastSource = readableSource;
        }
      }
    } catch (error) {
      signal?.throwIfAborted();
      sourceProbeFailed = error instanceof TypeError || error.code === "NETWORK_UNAVAILABLE" ||
        Boolean((publicationCheck || initialSourceFallback) && error.code === "INVALID_RESPONSE") ||
        Boolean(initialSourceFallback && error.status === 503 && error.retryable);
      if (!sourceProbeFailed && !([429, 503].includes(error.status) && error.retryable)) throw error;
      retryAfter = Number(error.retryAfterSeconds) || 0;
    }
    const remaining = deadline - now();
    if (remaining <= 0) break;
    if (statusProbe) {
      const regularWait = Math.max(0, statusProbe.regularReadAt - now());
      await wait(Math.min(remaining, Math.max(regularWait, retryAfter * 1000)), signal);
      continue;
    }
    if (firstReadAt) {
      const samePendingSource = shortSourceCheck && latest.data.article.processing.job_id === earlyConfirmationJob;
      const advancedReadStillPending = advancedProbeLimit && shortSourceCheck;
      if (initialSourceFallback && retryAfter === 0 && (samePendingSource || sourceProbeFailed || advancedReadStillPending)) {
        // A missed immediate check rejoins the original optional and regular reads.
        if (advancedProbeLimit) initialSourceFallbackAt = initialSourceFallback;
        const nextReadAt = advancedProbeLimit || initialSourceFallback;
        await wait(Math.min(remaining, Math.max(0, nextReadAt - now())), signal);
        continue;
      }
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
      initialSourceFallbackAt = scheduledAt + sourceProbeIntervalMs;
      nextSourceProbeAt = scheduledAt + 2 * sourceProbeIntervalMs;
      const elapsed = scheduledAt - (initialReadStartedAt ?? startedAt);
      backoff = initialSourceProbeDelayMs;
      // Advance a useful first check toward the original request's start.
      // An unanswered check still leaves the first scheduled probe in place.
      if (elapsed >= minimumSourceProbeAdvanceMs) {
        advancedSourceProbeUntil = scheduledAt + backoff;
        backoff = Math.max(0, backoff - elapsed);
      }
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
        const scheduledAt = now();
        publicationReadAt = scheduledAt + backoff;
        publicationProbeJob = shortPublicationJob;
        backoff = publicationProbeIntervalMs;
        const anchor = publicationAnchor(latest);
        if (anchor) {
          // Give an anchored rewrite one early opportunity. Keep both original
          // checks for a rewrite that is still active or an unanswered probe.
          scheduledPublicationCheck = { anchor, regularReadAt: scheduledAt + backoff, late: false };
          backoff = initialPublicationProbeDelayMs;
        }
      }
    }
    // Keep the regular read time while allowing one smaller check after any server hint.
    const anchor = readable && retryAfter * 1000 <= publicationStatusProbeDelayMs &&
      backoff >= 2 * publicationStatusProbeDelayMs && publicationAnchor(latest);
    const earlierProbe = anchor && publicationStatusProbes.get(anchor.jobId);
    // A confirmed slow rewrite gets one more compact check during the long
    // backoff. An error or mismatched response leaves the regular read intact.
    const checkLongBackoff = earlierProbe?.attempts === 1 && earlierProbe.confirmedPending &&
      earlierProbe.articleId === anchor.articleId && earlierProbe.sourceRevisionId === anchor.sourceRevisionId &&
      backoff >= latePublicationProbeMinimumBackoffMs;
    if (anchor && remaining > publicationStatusProbeDelayMs && (!earlierProbe || checkLongBackoff)) {
      publicationStatusProbes.set(anchor.jobId, {
        articleId: anchor.articleId,
        sourceRevisionId: anchor.sourceRevisionId,
        attempts: earlierProbe ? 2 : 1,
        confirmedPending: false,
      });
      scheduledPublicationCheck = { anchor, regularReadAt: now() + backoff, late: checkLongBackoff };
      backoff = publicationStatusProbeDelayMs;
    }
    // Check midway through the first long waits for a confirmed active capture.
    // If the check misses, keep the next ordinary read and its backoff.
    if ((backoff === 4000 || backoff === 8000) && fastPendingJob &&
        latest.data.article.processing.state === "fetching_source") {
      regularSourceReadAt = now() + backoff;
      backoff /= 2;
    }
    await wait(
      Math.min(remaining, Math.max(backoff, retryAfter * 1000)),
      signal,
    );
  }
  signal?.throwIfAborted();
  return { ...latest, timedOut: true };
}
