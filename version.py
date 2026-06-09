"""MacroForge version info — single source of truth."""

VERSION = "3.9.8"
VERSION_TUPLE = tuple(int(p) for p in VERSION.split(".") if p.isdigit())

# Increment this when shipping a patch rebuild under the same version.
# The updater checks BUILD_ID when VERSION is unchanged.
BUILD_ID = 7

# Update source (raw JSON hosted anywhere — GitHub raw, S3, your own server)
# Example: "https://raw.githubusercontent.com/YourUser/MacroForge/main/update.json"
UPDATE_URL = "https://raw.githubusercontent.com/xRampageous/MacroForge/main/update.json"

# Set this to the URL of your update JSON file to enable update checking.
# If left empty, update checking is silently skipped.
