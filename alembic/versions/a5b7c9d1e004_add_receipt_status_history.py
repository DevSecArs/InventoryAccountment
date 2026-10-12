"""add receipt status history

Revision ID: a5b7c9d1e004
Revises: f4a6c8d0e003
"""

from alembic import op
import sqlalchemy as sa

revision = "a5b7c9d1e004"
down_revision = "f4a6c8d0e003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "receipt_status_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("receipt_id", sa.String(36), sa.ForeignKey("receipts.id"), nullable=False),
        sa.Column("from_status", sa.String(16), nullable=False),
        sa.Column("to_status", sa.String(16), nullable=False),
        sa.Column(
            "changed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.UniqueConstraint("receipt_id", name="uq_receipt_status_history_receipt_id"),
    )
    op.create_index(
        "ix_receipt_status_history_receipt_changed_id",
        "receipt_status_history",
        ["receipt_id", "changed_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_receipt_status_history_receipt_changed_id", table_name="receipt_status_history")
    op.drop_table("receipt_status_history")
