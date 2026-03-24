import logging
import boto3
from datetime import datetime, timezone
from sqlalchemy import select
from db import SessionLocal
from models import Document, AuditEvent
from core.settings import settings

logger = logging.getLogger("smartitr")

s3_client = boto3.client('s3', region_name=settings.aws_region)

def delete_approved_pdfs() -> int:
    """
    Run periodically via APScheduler.
    Deletes raw PDFs for all approved documents, satisfying DPDP Act 
    data minimization requirements (Section 8).
    Keeps only the structured extracted JSON/computation data.
    """
    db = SessionLocal()
    deleted_count = 0
    try:
        bucket = f"smartitr-docs-{settings.aws_region}"
        
        # Find approved documents where the PDF hasn't been deleted yet
        query = select(Document).where(
            Document.status == "approved",
            Document.pdf_deleted == False
        )
        
        documents = db.scalars(query).all()
        
        for doc in documents:
            try:
                # 1. Delete from S3
                s3_client.delete_object(
                    Bucket=bucket,
                    Key=doc.s3_key
                )
                
                # 2. Update Document record
                doc.pdf_deleted = True
                doc.pdf_deleted_at = datetime.now(timezone.utc)
                
                # 3. Create immutable audit trail
                audit = AuditEvent(
                    firm_id=doc.firm_id,
                    action="pdf_erased",
                    resource_type="document",
                    resource_id=str(doc.id),
                    actor_type="system",
                    description="Raw PDF permanently deleted to comply with DPDP data minimization after CA approval.",
                    details={"s3_key": doc.s3_key}
                )
                
                db.add(audit)
                deleted_count += 1
                
            except Exception as e:
                logger.error(f"Failed to delete PDF {doc.s3_key}: {e}", exc_info=True)
                
        db.commit()
    finally:
        db.close()
        
    if deleted_count > 0:
        logger.info(f"DPDP Cleanup Complete: securely eradicated {deleted_count} raw PDFs.")
        
    return deleted_count
