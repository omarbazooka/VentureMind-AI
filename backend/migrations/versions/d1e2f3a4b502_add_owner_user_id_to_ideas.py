"""add owner_user_id to ideas

Revision ID: d1e2f3a4b502
Revises: c1a2d3e4f501
Create Date: 2026-09-10 01:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1e2f3a4b502'
down_revision: Union[str, None] = 'c1a2d3e4f501'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('ideas', sa.Column('owner_user_id', sa.Uuid(), nullable=True))
    op.create_index(op.f('ix_ideas_owner_user_id'), 'ideas', ['owner_user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_ideas_owner_user_id'), table_name='ideas')
    op.drop_column('ideas', 'owner_user_id')
