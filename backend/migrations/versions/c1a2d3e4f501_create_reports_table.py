"""create reports table

Revision ID: c1a2d3e4f501
Revises: b9bbca776d3b
Create Date: 2026-09-09 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c1a2d3e4f501'
down_revision: Union[str, None] = 'b9bbca776d3b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'reports',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('idea_id', sa.Uuid(), nullable=False),
        sa.Column('analysis_run_id', sa.Uuid(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('report_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['analysis_run_id'], ['analysis_runs.id']),
        sa.ForeignKeyConstraint(['idea_id'], ['ideas.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('idea_id', 'version', name='uq_reports_idea_id_version')
    )
    op.create_index(op.f('ix_reports_analysis_run_id'), 'reports', ['analysis_run_id'], unique=False)
    op.create_index(op.f('ix_reports_idea_id'), 'reports', ['idea_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_reports_idea_id'), table_name='reports')
    op.drop_index(op.f('ix_reports_analysis_run_id'), table_name='reports')
    op.drop_table('reports')
