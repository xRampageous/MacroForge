"""MacroForge version info — single source of truth."""

VERSION = "1.2.12"
VERSION_TUPLE = tuple(int(p) for p in VERSION.split(".") if p.isdigit())

# Update source (raw JSON hosted anywhere — GitHub raw, S3, your own server)
# Example: "https://raw.githubusercontent.com/YourUser/MacroForge/main/update.json"
UPDATE_URL = "https://raw.githubusercontent.com/xRampageous/MacroForge/main/update.json"

# Set this to the URL of your update JSON file to enable update checking.
# If left empty, update checking is silently skipped.
