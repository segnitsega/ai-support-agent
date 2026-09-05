/** Map raw API / browser errors to short copy safe for customers. */
export function friendlyError(raw: unknown): string {
  const text = String(
    raw instanceof Error ? raw.message : (raw ?? 'Something went wrong'),
  )
  const lowered = text.toLowerCase()

  if (
    lowered.includes('resource_exhausted') ||
    lowered.includes('quota') ||
    lowered.includes('rate limit') ||
    lowered.includes('429')
  ) {
    return "We're getting a lot of requests right now. Please wait a moment and try again."
  }

  if (
    lowered.includes('failed to fetch') ||
    lowered.includes('networkerror') ||
    lowered.includes('network request failed')
  ) {
    return 'Unable to reach support right now. Check your connection and try again.'
  }

  if (lowered.includes('timeout') || lowered.includes('timed out')) {
    return 'That took too long to answer. Please try again.'
  }

  // Already a short product message from the API — keep it.
  if (
    text.length <= 160 &&
    !lowered.includes('traceback') &&
    !lowered.includes('error calling model') &&
    !lowered.includes('{')
  ) {
    return text
  }

  return 'Something went wrong while processing your request. Please try again.'
}
