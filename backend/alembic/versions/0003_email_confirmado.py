"""email confirmado

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-25 22:38:21.208884
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("usuarios", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("email_confirmado", sa.Boolean(), server_default=sa.false(), nullable=False)
        )
    # Contas criadas antes da confirmação por e-mail continuam entrando normalmente.
    op.execute(sa.text("UPDATE usuarios SET email_confirmado = :sim").bindparams(sim=True))


def downgrade() -> None:
    with op.batch_alter_table("usuarios", schema=None) as batch_op:
        batch_op.drop_column("email_confirmado")
