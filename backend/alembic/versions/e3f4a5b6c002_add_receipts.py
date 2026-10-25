"""add receipt drafts

Revision ID: e3f4a5b6c002
Revises: d2a2c780d001
"""

from alembic import op
import sqlalchemy as sa

revision = "e3f4a5b6c002"
down_revision = "d2a2c780d001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "receipts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("supplier_id", sa.String(36), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("document_number", sa.String(64), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=True, unique=True),
        sa.Column("error_message", sa.String(500)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("supplier_id", "document_number"),
        sa.CheckConstraint("status IN ('draft', 'queued', 'processing', 'posted', 'failed')"),
    )
    op.create_index("ix_receipts_status_received_at", "receipts", ["status", "received_at"])
    op.create_index("ix_receipts_supplier_received_at", "receipts", ["supplier_id", "received_at"])
    op.create_table(
        "receipt_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "receipt_id",
            sa.String(36),
            sa.ForeignKey("receipts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("material_id", sa.String(36), sa.ForeignKey("materials.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 3), nullable=False),
        sa.UniqueConstraint("receipt_id", "material_id"),
        sa.CheckConstraint("quantity > 0"),
    )
    op.create_index("ix_receipt_items_material_id", "receipt_items", ["material_id"])


def downgrade() -> None:
    op.drop_index("ix_receipt_items_material_id", table_name="receipt_items")
    op.drop_table("receipt_items")
    op.drop_index("ix_receipts_supplier_received_at", table_name="receipts")
    op.drop_index("ix_receipts_status_received_at", table_name="receipts")
    op.drop_table("receipts")
