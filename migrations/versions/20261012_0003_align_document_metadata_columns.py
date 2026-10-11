"""align document metadata column names

Revision ID: 20261012_0003
Revises: 20261012_0002
Create Date: 2026-10-12 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20261012_0003"
down_revision = "20261012_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    column_names = {column["name"] for column in sa.inspect(bind).get_columns("document_metadata")}
    renames = (
        ("author", "teu"),
        ("short_form", "form_short"),
        ("place_enactment", "place_of_enactment"),
        ("date_enacted", "enactment_date"),
        ("date_promulgated", "promulgation_date"),
        ("date_effective", "effective_date"),
    )

    for old_name, new_name in renames:
        if old_name in column_names and new_name not in column_names:
            with op.batch_alter_table("document_metadata") as batch_op:
                batch_op.alter_column(old_name, new_column_name=new_name)
            column_names.remove(old_name)
            column_names.add(new_name)


def downgrade() -> None:
    bind = op.get_bind()
    column_names = {column["name"] for column in sa.inspect(bind).get_columns("document_metadata")}
    renames = (
        ("teu", "author"),
        ("form_short", "short_form"),
        ("place_of_enactment", "place_enactment"),
        ("enactment_date", "date_enacted"),
        ("promulgation_date", "date_promulgated"),
        ("effective_date", "date_effective"),
    )

    for old_name, new_name in renames:
        if old_name in column_names and new_name not in column_names:
            with op.batch_alter_table("document_metadata") as batch_op:
                batch_op.alter_column(old_name, new_column_name=new_name)
            column_names.remove(old_name)
            column_names.add(new_name)