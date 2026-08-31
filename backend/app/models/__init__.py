"""Modelos do banco. Importar todos aqui para o Alembic enxergar o metadata."""

from app.models.alert import Alert, Inspection, Maintenance
from app.models.hierarchy import Area, Line, Plant
from app.models.measurement import Measurement, Prediction
from app.models.ml_model import MLModel
from app.models.motor import Motor
from app.models.refresh_token import RefreshToken
from app.models.user import AuditLog, User

__all__ = [
    "Alert", "Area", "AuditLog", "Inspection", "Line", "Maintenance", "Measurement",
    "MLModel", "Motor", "Plant", "Prediction", "RefreshToken", "User",
]
