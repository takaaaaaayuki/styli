from models import User
from database import SessionLocal
from sqlalchemy.orm import Session
from passlib.hash import bcrypt

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def register_user(username: str, password: str):
    db: Session = next(get_db())
    hashed = bcrypt.hash(password)
    user = User(username=username, hashed_password=hashed)
    db.add(user)
    db.commit()

def authenticate_user(username: str, password: str) -> bool:
    db: Session = next(get_db())
    user = db.query(User).filter(User.username == username).first()
    if user and bcrypt.verify(password, user.hashed_password):
        return True
    return False
