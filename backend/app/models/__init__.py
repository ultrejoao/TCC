"""Modelos do banco. Importar todos aqui para o Alembic enxergar o metadata."""

from app.models.alert import Alert, Inspection, Maintenance
from app.models.measurement import Measurement, Prediction
from app.models.ml_model import MLModel
from app.models.motor import Motor, Sector
from app.models.user import AuditLog, User

__all__ = [
    "Alert", "AuditLog", "Inspection", "Maintenance", "Measurement",
    "MLModel", "Motor", "Prediction", "Sector", "User",
]
