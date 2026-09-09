"""Registra a unidade em que o sinal foi enviado

Sem ela o arquivo bruto arquivado nao pode ser reinterpretado: os mesmos numeros
valem 1 ou 9,80665 conforme tenham sido declarados em g ou m/s^2. Medicoes
anteriores ficam com NULL, e o leitor assume m/s^2 nesse caso.

Revision ID: e5f13c8a47b2
Revises: d4e92a05b13f
"""

import sqlalchemy as sa
from alembic import op

revision = "e5f13c8a47b2"
down_revision = "d4e92a05b13f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("measurements",
                  sa.Column("source_unit", sa.String(length=10), nullable=True))


def downgrade() -> None:
    op.drop_column("measurements", "source_unit")
