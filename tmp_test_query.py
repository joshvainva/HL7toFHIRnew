import os
from dotenv import load_dotenv
load_dotenv()
from app.db.session import SessionLocal
from app.models.db_models import ConversionLog
from sqlalchemy import cast, Text

def check_db():
    db = SessionLocal()
    pattern = '%\\"birthDate\\": \\"1992-04-12%'
    logs = db.query(ConversionLog).filter(cast(ConversionLog.fhir_bundle, Text).ilike(pattern)).all()
    print("For pattern:", pattern, "found logs:", len(logs))
    
    # What does the bundle actually look like as text?
    sample = db.query(ConversionLog).first()
    print("Sample output cast as String to show spacing details:")
    row = db.query(cast(ConversionLog.fhir_bundle, Text)).first()
    print(row[0][:300])

if __name__ == "__main__":
    check_db()
