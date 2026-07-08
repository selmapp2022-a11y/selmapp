"""Add 'apple' to oauthprovider enum.

Revision ID: 20260707_apple_oauth
Revises: 20260502_revenuecat
Create Date: 2026-07-07

The `oauthprovider` PostgreSQL enum was originally created in migration
2f6763813ba0 with only ('google', 'github', 'facebook'). Sign in with
Apple, wired end-to-end in Build 35 (2.0.4) of the iOS app, then blew
up in production with:

    asyncpg.exceptions.InvalidTextRepresentationError:
      invalid input value for enum oauthprovider: "apple"

...on the very first Apple sign-in attempt from Apple's review team.
That's what caused iOS rejection under Guideline 2.1(a) — App
Completeness ("An error message displayed after we logged in through
the 'Sign in with Apple' option.").

Fix: add the 'apple' value to the enum. Paired with a Python model
update in app/models/user.py that adds APPLE = "apple" to the
OAuthProvider enum class.

## Why `ALTER TYPE ... ADD VALUE` and not a full rewrite

PostgreSQL 12+ allows adding new enum values inside a transaction, so
alembic's default transactional migration works here. `IF NOT EXISTS`
makes the migration idempotent — safe to re-run against a database
that's already been patched by hand.
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260707_apple_oauth"
down_revision: Union[str, Sequence[str], None] = "20260502_revenuecat"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # `ADD VALUE IF NOT EXISTS` is Postgres 9.6+.
    op.execute("ALTER TYPE oauthprovider ADD VALUE IF NOT EXISTS 'apple'")


def downgrade() -> None:
    # PostgreSQL does not support removing values from an enum type.
    # Removing 'apple' would require:
    #   1. Rename old enum: ALTER TYPE oauthprovider RENAME TO oauthprovider_old
    #   2. Create new enum without 'apple'
    #   3. Alter oauth2_accounts.provider column to use new enum with USING clause
    #   4. Drop old enum
    # Not worth the complexity for a downgrade path we'll never take.
    pass
