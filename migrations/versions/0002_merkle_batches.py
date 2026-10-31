"""Persist complete, immutable Merkle batches and ordered registration snapshots."""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "merkle_batches",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("root", sa.Text(), nullable=False),
        sa.Column("tree_size", sa.Integer(), nullable=False),
        sa.Column("merkle_version", sa.Text(), nullable=False),
        sa.Column("sealed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("tree_size > 0 AND tree_size <= 1000", name="ck_batches_size"),
        sa.CheckConstraint("root ~ '^[0-9a-f]{64}$'", name="ck_batches_root"),
        sa.CheckConstraint("merkle_version = 'rootproof.merkle.rfc9162.sha256.v1'", name="ck_batches_version"),
    )
    op.create_table(
        "batch_entries",
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("registration_id", sa.Uuid(), nullable=False),
        sa.Column("entry_bytes", sa.LargeBinary(), nullable=False),
        sa.PrimaryKeyConstraint("batch_id", "position"),
        sa.ForeignKeyConstraint(["batch_id"], ["merkle_batches.id"]),
        sa.ForeignKeyConstraint(["registration_id"], ["registrations.id"]),
        sa.UniqueConstraint("registration_id", name="uq_batch_entries_registration"),
        sa.CheckConstraint("position >= 0", name="ck_entries_position"),
        sa.CheckConstraint("octet_length(entry_bytes) > 0", name="ck_entries_bytes"),
    )
    op.execute("""
        CREATE FUNCTION rootproof_forbid_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Sealed integrity data cannot be changed'
                USING ERRCODE = '23514';
        END $$
    """)
    for table in ("merkle_batches", "batch_entries"):
        op.execute(f"CREATE TRIGGER rootproof_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION rootproof_forbid_mutation()")
    for table in ("merkle_batches", "batch_entries", "registrations"):
        op.execute(f"CREATE TRIGGER rootproof_no_truncate BEFORE TRUNCATE ON {table} FOR EACH STATEMENT EXECUTE FUNCTION rootproof_forbid_mutation()")
    op.execute("""
        CREATE FUNCTION rootproof_protect_registration() RETURNS trigger
        LANGUAGE plpgsql SET search_path FROM CURRENT AS $$
        BEGIN
            IF EXISTS (SELECT 1 FROM batch_entries WHERE registration_id = OLD.id) THEN
                RAISE EXCEPTION 'Batched registrations cannot be changed'
                    USING ERRCODE = '23514';
            END IF;
            IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END $$
    """)
    op.execute("CREATE TRIGGER rootproof_registration_guard BEFORE UPDATE OR DELETE ON registrations FOR EACH ROW EXECUTE FUNCTION rootproof_protect_registration()")
    op.execute("""
        CREATE FUNCTION rootproof_entry_bounds() RETURNS trigger
        LANGUAGE plpgsql SET search_path FROM CURRENT AS $$
        DECLARE expected_size integer;
        BEGIN
            SELECT tree_size INTO expected_size FROM merkle_batches
                WHERE id = NEW.batch_id FOR UPDATE;
            IF expected_size IS NULL OR NEW.position >= expected_size THEN
                RAISE EXCEPTION 'Batch entry position is outside the sealed tree'
                    USING ERRCODE = '23514';
            END IF;
            PERFORM 1 FROM registrations WHERE id = NEW.registration_id FOR UPDATE;
            RETURN NEW;
        END $$
    """)
    op.execute("CREATE TRIGGER rootproof_entry_guard BEFORE INSERT ON batch_entries FOR EACH ROW EXECUTE FUNCTION rootproof_entry_bounds()")
    op.execute("""
        CREATE FUNCTION rootproof_check_batch_complete() RETURNS trigger
        LANGUAGE plpgsql SET search_path FROM CURRENT AS $$
        BEGIN
            IF (SELECT count(*) FROM batch_entries WHERE batch_id = NEW.id) <> NEW.tree_size THEN
                RAISE EXCEPTION 'A sealed batch must contain every declared entry'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END $$
    """)
    op.execute("""
        CREATE CONSTRAINT TRIGGER rootproof_batch_complete AFTER INSERT ON merkle_batches
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
        EXECUTE FUNCTION rootproof_check_batch_complete()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER rootproof_registration_guard ON registrations")
    op.execute("DROP TRIGGER rootproof_no_truncate ON registrations")
    op.drop_table("batch_entries")
    op.drop_table("merkle_batches")
    for name in ("rootproof_check_batch_complete", "rootproof_entry_bounds", "rootproof_protect_registration", "rootproof_forbid_mutation"):
        op.execute(f"DROP FUNCTION {name}()")
