"""Make the test suite importable.

`app.core.config.Settings` requires ADMIN_OWNER_PASSWORD and
ADMIN_DEV_PASSWORD with no defaults — correct for a deployment, and it meant
that importing anything under `app.` raised before a single test ran. Every
test file in this directory was therefore uncollectable on a clean checkout.

That is worth naming rather than quietly fixing: a suite nobody can run is the
same defect as a parameter nobody passes. It looks like coverage from the
outside.

These are obvious non-secrets, set only for the duration of a test process, and
they must stay obvious: if one of these strings ever appears in a deployment,
the deployment is misconfigured and should look it.
"""
import os

os.environ.setdefault("ADMIN_OWNER_PASSWORD", "test-only-not-a-real-password")
os.environ.setdefault("ADMIN_DEV_PASSWORD", "test-only-not-a-real-password")
os.environ.setdefault("ENVIRONMENT", "test")
