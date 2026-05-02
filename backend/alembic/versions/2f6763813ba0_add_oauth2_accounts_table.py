"""add oauth2 accounts table

Revision ID: 2f6763813ba0
Revises: 6a376cb460f9
Create Date: 2025-07-03 17:53:15.046809

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '2f6763813ba0'
down_revision: Union[str, None] = '6a376cb460f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create OAuth2 provider enum if it doesn't exist
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE oauthprovider AS ENUM ('google', 'github', 'facebook');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Create oauth2_accounts table using raw SQL to avoid enum creation issues
    op.execute("""
        CREATE TABLE oauth2_accounts (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            provider oauthprovider NOT NULL,
            provider_user_id VARCHAR(255) NOT NULL,
            provider_email VARCHAR(255),
            provider_name VARCHAR(255),
            provider_avatar_url VARCHAR(500),
            access_token VARCHAR(1000),
            refresh_token VARCHAR(1000),
            token_expires_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ
        )
    """)
    
    # Create indexes
    op.execute("CREATE INDEX ix_oauth2_accounts_id ON oauth2_accounts (id)")
    op.execute("CREATE INDEX ix_oauth2_accounts_user_id ON oauth2_accounts (user_id)")
    op.execute("CREATE UNIQUE INDEX ix_oauth2_accounts_provider_user_id ON oauth2_accounts (provider, provider_user_id)")


def downgrade() -> None:
    """Downgrade schema."""
    # Drop oauth2_accounts table
    op.execute("DROP TABLE IF EXISTS oauth2_accounts")
    
    # Drop OAuth2 provider enum
    op.execute("DROP TYPE IF EXISTS oauthprovider")
