"""Add RevenueCat columns to subscriptions and merge open heads.

Revision ID: 20260502_revenuecat
Revises: 20260214_merge_heads, 20251229_add_personalization
Create Date: 2026-05-02

Adds RevenueCat-specific columns to the subscriptions table so the same
row can represent either a legacy PayPal subscription or a RevenueCat
subscription (mobile App Store / Play Store / Web Billing).

Idempotent: each ALTER checks whether the column exists first so the
migration is safe to re-run if the database is partially up to date.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260502_revenuecat"
down_revision: Union[str, Sequence[str], None] = (
    "20260214_merge_heads",
    "20251229_add_personalization",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return table in insp.get_table_names()


def _existing_columns(table: str) -> set:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    # Defensive: in some environments the `subscriptions` table was never
    # created (the earlier payments migration was skipped). In that case
    # we skip silently — the table will be created by its own migration
    # later, including the columns added below.
    if not _table_exists("subscriptions"):
        return

    cols = _existing_columns("subscriptions")

    if "provider" not in cols:
        op.add_column(
            "subscriptions",
            sa.Column(
                "provider",
                sa.String(length=20),
                nullable=False,
                server_default="paypal",
            ),
        )
    if "rc_app_user_id" not in cols:
        op.add_column(
            "subscriptions",
            sa.Column("rc_app_user_id", sa.String(length=255), nullable=True),
        )
        op.create_index(
            "ix_subscriptions_rc_app_user_id",
            "subscriptions",
            ["rc_app_user_id"],
        )
    if "rc_entitlement" not in cols:
        op.add_column(
            "subscriptions",
            sa.Column("rc_entitlement", sa.String(length=100), nullable=True),
        )
    if "rc_product_id" not in cols:
        op.add_column(
            "subscriptions",
            sa.Column("rc_product_id", sa.String(length=255), nullable=True),
        )
    if "rc_period_type" not in cols:
        op.add_column(
            "subscriptions",
            sa.Column("rc_period_type", sa.String(length=20), nullable=True),
        )
    if "rc_store" not in cols:
        op.add_column(
            "subscriptions",
            sa.Column("rc_store", sa.String(length=20), nullable=True),
        )


def downgrade() -> None:
    cols = _existing_columns("subscriptions")
    if "rc_store" in cols:
        op.drop_column("subscriptions", "rc_store")
    if "rc_period_type" in cols:
        op.drop_column("subscriptions", "rc_period_type")
    if "rc_product_id" in cols:
        op.drop_column("subscriptions", "rc_product_id")
    if "rc_entitlement" in cols:
        op.drop_column("subscriptions", "rc_entitlement")
    if "rc_app_user_id" in cols:
        try:
            op.drop_index("ix_subscriptions_rc_app_user_id", "subscriptions")
        except Exception:
            pass
        op.drop_column("subscriptions", "rc_app_user_id")
    if "provider" in cols:
        op.drop_column("subscriptions", "provider")
