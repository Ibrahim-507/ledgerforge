
"""create org tables

Revision ID: 8ba012839fa4
Revises:
"""

from alembic import op
import sqlalchemy as sa

# Alembic revision identifiers
revision = "8ba012839fa4"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create departments table."""

    op.create_table(
        "departments",
        sa.Column(
            "department_id",
            sa.String(length=10),
            nullable=False
        ),
        sa.Column(
            "department_name",
            sa.String(length=100),
            nullable=False
        ),
        sa.Column(
            "cost_center",
            sa.String(length=20),
            nullable=False
        ),
        sa.Column(
            "description",
            sa.String(length=300),
            nullable=True
        ),
        sa.PrimaryKeyConstraint("department_id")
    )


def downgrade() -> None:
    """Remove departments table."""

    op.drop_table("departments")
