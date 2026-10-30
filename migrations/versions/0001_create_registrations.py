"""Create hash registrations without source document storage."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "registrations",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("digest", sa.Text(), nullable=False),
        sa.Column("hash_algorithm", sa.String(16), server_default="sha256", nullable=False),
        sa.Column("registration_metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.text("statement_timestamp()"), nullable=False),
        sa.Column("format_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("hash_algorithm = 'sha256'", name="ck_registrations_algorithm"),
        sa.CheckConstraint("digest ~ '^[0-9a-f]{64}$'", name="ck_registrations_digest"),
        sa.CheckConstraint("format_version = 1", name="ck_registrations_version"),
        sa.CheckConstraint("jsonb_typeof(registration_metadata) = 'object'", name="ck_registrations_metadata_object"),
        sa.CheckConstraint("octet_length(registration_metadata::text) <= 8192", name="ck_registrations_metadata_size"),
    )


def downgrade() -> None:
    op.drop_table("registrations")
