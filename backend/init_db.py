import sys
import os

from db import engine
from models.base import Base

# Import all models to ensure they are registered with Base.metadata
from models.audit_event import AuditEvent
from models.client import Client
from models.consent_record import ConsentRecord
from models.export_artifact import ExportArtifact
from models.firm import Firm
from models.user import User
from models.document import Document
from models.validation_finding import ValidationFinding
from models.upload_token import UploadToken

def init_db():
    print(f"Creating tables in database: {engine.url.database}...")
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully.")

if __name__ == "__main__":
    init_db()
