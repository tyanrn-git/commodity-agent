import secrets
from datetime import datetime, timedelta, timezone

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.domain.models import Session as UserSession
from app.domain.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_session(db: Session, user: User) -> UserSession:
    session = UserSession(
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=settings.session_max_age_seconds),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session_by_id(db: Session, session_id: str) -> UserSession | None:
    try:
        import uuid

        sid = uuid.UUID(session_id)
    except ValueError:
        return None
    stmt = (
        select(UserSession)
        .where(UserSession.id == sid)
        .options(joinedload(UserSession.user))
    )
    return db.scalar(stmt)


def get_valid_session(db: Session, session_id: str) -> UserSession | None:
    session = get_session_by_id(db, session_id)
    if session is None:
        return None
    if session.expires_at < datetime.now(timezone.utc):
        db.delete(session)
        db.commit()
        return None
    return session


def delete_session(db: Session, session: UserSession) -> None:
    db.delete(session)
    db.commit()


def get_user_by_email(db: Session, email: str) -> User | None:
    stmt = select(User).where(User.email == email)
    return db.scalar(stmt)


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = get_user_by_email(db, email)
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def ensure_admin_user(db: Session) -> User:
    user = get_user_by_email(db, settings.admin_email)
    if user:
        return user
    user = User(
        email=settings.admin_email,
        password_hash=hash_password(settings.admin_password),
        timezone="Atlantic/Madeira",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def generate_deal_number() -> str:
    return f"D-{secrets.token_hex(4).upper()}"
