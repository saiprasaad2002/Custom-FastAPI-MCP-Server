from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()

class Application(Base):
    __tablename__ = 'applications'
    
    id = Column(Integer, primary_key=True)
    email = Column(String)
    resume_content = Column(Text)
    job_description = Column(Text)
    score = Column(Float)
    email_status = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)

class ErrorLog(Base):
    __tablename__ = 'error_logs'
    
    id = Column(Integer, primary_key=True)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

engine = create_engine('sqlite:///applications.db')
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def save_application(email: str, resume_content: str, job_description: str, score: float, email_status: bool = False) -> bool:
    db = SessionLocal()
    try:
        application = Application(
            email=email,
            resume_content=resume_content,
            job_description=job_description,
            score=score,
            email_status=email_status
        )
        db.add(application)
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False
    finally:
        db.close()

def get_application_by_email(email: str):
    db = SessionLocal()
    try:
        return db.query(Application).filter(Application.email == email).first()
    finally:
        db.close()

def get_application_by_resume(resume_content: str):
    db = SessionLocal()
    try:
        return db.query(Application).filter(Application.resume_content == resume_content).first()
    finally:
        db.close()

def insert_error_log(error_message: str):
    db = SessionLocal()
    try:
        error_log = ErrorLog(error_message=error_message)
        db.add(error_log)
        db.commit()
    finally:
        db.close()

def update_email_status(email: str, status: bool) -> bool:
    db = SessionLocal()
    try:
        application = db.query(Application).filter(Application.email == email).first()
        if application:
            application.email_status = status
            db.commit()
            return True
        return False
    except Exception:
        db.rollback()
        return False
    finally:
        db.close()

def get_exact_application_match(email: str, resume_content: str, job_description: str):
    """
    Get application that matches exactly on email, resume content, and job description.
    """
    db = SessionLocal()
    try:
        return db.query(Application).filter(
            Application.email == email,
            Application.resume_content == resume_content,
            Application.job_description == job_description
        ).first()
    finally:
        db.close() 