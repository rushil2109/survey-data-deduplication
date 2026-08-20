from __future__ import annotations

import argparse
import logging
import os

from .api_client import ApiError, SurveyApiClient
from .input_reader import read_responses

logger = logging.getLogger(__name__)


def chunks(items: list, size: int):
    # Split a list into fixed-size batches. Batching limits request size and
    # isolates failures — if one batch is rejected, later batches still proceed.
    for start in range(0, len(items), size):
        yield items[start : start + size]


def run(args: argparse.Namespace) -> int:
    # Main pipeline: read → authenticate → query existing → deduplicate → upload.
    # Authentication failure is fatal; query/upload failures are logged per batch.
    if args.query_batch_size < 1 or args.upload_batch_size < 1:
        logger.error("Batch sizes must be positive")
        return 1
    try:
        responses, skipped = read_responses(args.input)
        client = SurveyApiClient(args.base_url, args.client_id, args.client_secret, args.timeout)
        client.authenticate()
    except (ValueError, ApiError) as exc:
        logger.error("Fatal error: %s", exc)
        return 1

    existing: set[str] = set()
    query_failed_ids: set[str] = set()
    for batch in chunks(responses, args.query_batch_size):
        batch_ids = [str(response.responseId) for response in batch]
        try:
            existing.update(client.existing_response_ids(batch_ids))
        except ApiError as exc:
            # If the duplicate-check query fails for a batch, we cannot know whether
            # those records already exist. Uploading them risks creating duplicates, so
            # they are excluded from the upload entirely and logged for investigation.
            # TODO: persist progress so a re-run can retry just the failed query batches
            # rather than reprocessing the whole file.
            query_failed_ids.update(batch_ids)
            logger.error("Duplicate query failed for response_ids=%s: %s", batch_ids, exc)

    # Filter before upload so the mutation only receives genuinely new records.
    # A production backend would enforce a UNIQUE constraint on responseId, so any
    # duplicate that slipped through (e.g. from a concurrent run) would be a hard
    # error rather than a silent overwrite — but the client-side filter is the first
    # line of defence and avoids unnecessary write load.
    new_responses = [
        response
        for response in responses
        if str(response.responseId) not in existing and str(response.responseId) not in query_failed_ids
    ]
    failed_batches = 0
    uploaded = 0
    for batch in chunks(new_responses, args.upload_batch_size):
        try:
            uploaded += len(client.upload([response.as_dict() for response in batch]))
        except ApiError as exc:
            # One failed batch does not stop the run; later batches may succeed.
            # TODO: retry failed batches record-by-record to isolate the bad record
            # instead of skipping the whole batch.
            failed_batches += 1
            logger.error("Upload batch failed for response_ids=%s: %s", [str(response.responseId) for response in batch], exc)

    logger.info("Summary: read=%d skipped=%d existing=%d new=%d uploaded=%d failed_batches=%d", len(responses) + skipped, skipped, len(existing), len(new_responses), uploaded, failed_batches)
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Deduplicate and upload survey responses")
    result.add_argument("input", help="JSON input file")
    result.add_argument("--base-url", default=os.getenv("API_BASE_URL", "http://127.0.0.1:5000"))
    result.add_argument("--client-id", default=os.getenv("CLIENT_ID", "demo-client"))
    result.add_argument("--client-secret", default=os.getenv("CLIENT_SECRET", "demo-secret"))
    result.add_argument("--timeout", type=float, default=float(os.getenv("REQUEST_TIMEOUT_SECONDS", "10")))
    result.add_argument("--query-batch-size", type=int, default=int(os.getenv("QUERY_BATCH_SIZE", "100")))
    result.add_argument("--upload-batch-size", type=int, default=int(os.getenv("UPLOAD_BATCH_SIZE", "100")))
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    options = parser().parse_args()
    raise SystemExit(run(options))