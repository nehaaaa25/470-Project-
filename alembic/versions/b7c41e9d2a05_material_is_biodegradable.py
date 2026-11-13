"""material categories: is_biodegradable (for the AI waste scanner)

Revision ID: b7c41e9d2a05
Revises: 69b99fcab333
Create Date: 2026-11-13 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7c41e9d2a05'
down_revision: Union[str, Sequence[str], None] = '69b99fcab333'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Sample materials from scripts/seed_demo.py that break down naturally.
# Databases that were seeded before this column existed get them ticked here.
SEEDED_BIODEGRADABLE = ("Paper & Cardboard", "Food & Garden Waste")


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('material_categories') as batch_op:
        batch_op.add_column(sa.Column('is_biodegradable', sa.Boolean(), nullable=False, server_default=sa.false()))

    categories = sa.table('material_categories', sa.column('name', sa.String), sa.column('is_biodegradable', sa.Boolean))
    op.execute(
        categories.update()
        .where(categories.c.name.in_(SEEDED_BIODEGRADABLE))
        .values(is_biodegradable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('material_categories') as batch_op:
        batch_op.drop_column('is_biodegradable')
