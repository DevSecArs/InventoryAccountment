"""enforce receipt document number invariant

Revision ID: f4a6c8d0e003
Revises: e3f4a5b6c002
"""

from alembic import op
import sqlalchemy as sa

revision = "f4a6c8d0e003"
down_revision = "e3f4a5b6c002"
branch_labels = None
depends_on = None


def _raise_if_incompatible_rows(connection: sa.Connection) -> None:
    blank_receipt = connection.execute(
        sa.text("SELECT id FROM receipts WHERE btrim(document_number) = '' LIMIT 1")
    ).scalar_one_or_none()
    if blank_receipt is not None:
        raise RuntimeError(
            "Нельзя применить миграцию: у поступления "
            f"{blank_receipt} пустой номер документа"
        )

    duplicate = connection.execute(
        sa.text(
            """
            SELECT supplier_id, btrim(document_number) AS document_number
            FROM receipts
            GROUP BY supplier_id, btrim(document_number)
            HAVING count(*) > 1
            LIMIT 1
            """
        )
    ).mappings().first()
    if duplicate is not None:
        raise RuntimeError(
            "Нельзя применить миграцию: после нормализации номер "
            f"{duplicate['document_number']!r} повторяется у поставщика {duplicate['supplier_id']}"
        )


def upgrade() -> None:
    connection = op.get_bind()
    _raise_if_incompatible_rows(connection)
    connection.execute(
        sa.text(
            "UPDATE receipts SET document_number = btrim(document_number) "
            "WHERE document_number <> btrim(document_number)"
        )
    )
    op.create_check_constraint(
        "ck_receipts_document_number_not_blank",
        "receipts",
        "btrim(document_number) <> ''",
    )


def downgrade() -> None:
    op.drop_constraint("ck_receipts_document_number_not_blank", "receipts", type_="check")
