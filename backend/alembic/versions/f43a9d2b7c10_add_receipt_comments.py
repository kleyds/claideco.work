"""add receipt comments

Revision ID: f43a9d2b7c10
Revises: e864ea5fcdb6
Create Date: 2026-05-09 23:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f43a9d2b7c10"
down_revision: Union[str, None] = "e864ea5fcdb6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("receipts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("upload_link_id", sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f("ix_receipts_upload_link_id"), ["upload_link_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_receipts_upload_link_id_client_upload_links",
            "client_upload_links",
            ["upload_link_id"],
            ["id"],
        )

    op.create_table(
        "receipt_comments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("receipt_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("author_type", sa.String(length=20), nullable=False),
        sa.Column("author_name", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_read_by_bookkeeper", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.ForeignKeyConstraint(["receipt_id"], ["receipts.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("receipt_comments", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_receipt_comments_client_id"), ["client_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_receipt_comments_id"), ["id"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_receipt_comments_is_read_by_bookkeeper"),
            ["is_read_by_bookkeeper"],
            unique=False,
        )
        batch_op.create_index(batch_op.f("ix_receipt_comments_receipt_id"), ["receipt_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_receipt_comments_user_id"), ["user_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("receipt_comments", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_receipt_comments_user_id"))
        batch_op.drop_index(batch_op.f("ix_receipt_comments_receipt_id"))
        batch_op.drop_index(batch_op.f("ix_receipt_comments_is_read_by_bookkeeper"))
        batch_op.drop_index(batch_op.f("ix_receipt_comments_id"))
        batch_op.drop_index(batch_op.f("ix_receipt_comments_client_id"))
    op.drop_table("receipt_comments")

    with op.batch_alter_table("receipts", schema=None) as batch_op:
        batch_op.drop_constraint("fk_receipts_upload_link_id_client_upload_links", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_receipts_upload_link_id"))
        batch_op.drop_column("upload_link_id")
