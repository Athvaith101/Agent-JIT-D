"""Vercel FastAPI entry point for a protected, non-durable demo deployment."""
import os

# Vercel Functions have read-only project filesystems. Keep demo state in scratch.
os.environ.setdefault("JITD_DATA_DIR", "/tmp/jitd-data")
os.environ.setdefault("JITD_REQUIRE_AUTH", "1")
os.environ.setdefault("JITD_MAX_MODEL_CALLS", "0")

# Live calls on an ephemeral multi-instance host cannot enforce a global ceiling.
if os.environ.get('JITD_MAX_MODEL_CALLS', '0') != '0':
    raise RuntimeError('Vercel preview requires JITD_MAX_MODEL_CALLS=0; use the persistent Render deployment for live calls.')
os.environ['JITD_HOST_MODE'] = 'ephemeral_preview'

from jitd.server import app  # noqa: E402
