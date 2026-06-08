# Experimental Features

This file tracks intentionally preserved future hooks that are not part of the
current runtime path.

## AIImageMatcher

`AIImageMatcher.py` is reserved for future semantic image matching. It wraps an
ONNX detector so a future image action could search for UI elements by label
instead of only by screenshot template.

Current status:

- Not wired into playback.
- No model is bundled.
- No extra runtime dependencies are required by the current app.
- Keep it out of release-critical paths until the feature is designed, tested,
  and documented.
