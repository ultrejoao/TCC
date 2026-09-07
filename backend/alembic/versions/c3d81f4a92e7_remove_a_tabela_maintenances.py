"""Remove a tabela maintenances

A tabela foi criada no schema inicial e nunca ganhou rota, tela ou registro:
zero linhas em producao. Historico de intervencao e uma funcionalidade legitima
de um sistema de manutencao preditiva, mas nao sustenta nenhuma pergunta deste
trabalho — ao contrario de `inspections`, que carrega a confirmacao de campo do
tipo de falha e por isso permanece.

Schema morto nao e neutro: sugere uma capacidade que o sistema nao tem e obriga
quem le o modelo de dados a descobrir sozinho que nada escreve ali.

O downgrade recria a tabela na forma exata em que existia, entao a decisao e
reversivel. Nao ha dados a preservar.

Revision ID: c3d81f4a92e7
Revises: 7a6a5d1822db
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c3d81f4a92e7"
down_revision = "7a6a5d1822db"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # drop_table remove os indices junto; sao listados aqui apenas para que o
    # downgrade os recrie identicos aos da migration inicial.
    op.drop_table("maintenances")


def downgrade() -> None:
    op.create_table(
        "maintenances",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("motor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("performed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("maintenance_type", sa.String(length=40), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("parts_replaced", sa.Text(), nullable=True),
        sa.Column("downtime_hours", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["motor_id"], ["motors.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_maintenances_created_at"), "maintenances", ["created_at"])
    op.create_index(op.f("ix_maintenances_motor_id"), "maintenances", ["motor_id"])
    op.create_index(op.f("ix_maintenances_performed_at"), "maintenances", ["performed_at"])
