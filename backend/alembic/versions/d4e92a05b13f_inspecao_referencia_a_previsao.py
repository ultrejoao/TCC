"""Inspecao referencia a previsao que confirma

Sem este vinculo, medir o acerto em campo exigiria reconstruir por data qual
previsao cada inspecao estava confirmando — uma heuristica que erra sempre que
houver mais de uma medicao no intervalo.

O vinculo e opcional: uma inspecao pode registrar um achado sem confirmar
nenhum diagnostico. So as que apontam para uma previsao entram no calculo de
acerto de campo.

Revision ID: d4e92a05b13f
Revises: c3d81f4a92e7
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d4e92a05b13f"
down_revision = "c3d81f4a92e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("inspections",
                  sa.Column("prediction_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index(op.f("ix_inspections_prediction_id"), "inspections", ["prediction_id"])
    op.create_foreign_key("fk_inspections_prediction_id", "inspections", "predictions",
                          ["prediction_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    op.drop_constraint("fk_inspections_prediction_id", "inspections", type_="foreignkey")
    op.drop_index(op.f("ix_inspections_prediction_id"), table_name="inspections")
    op.drop_column("inspections", "prediction_id")
