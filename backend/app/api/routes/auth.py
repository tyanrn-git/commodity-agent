from fastapi import APIRouter, Cookie, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas import LoginRequest, UpdateProfileRequest, UserResponse
from app.config import settings
from app.db.session import get_db
from app.domain.enums import AuditAction
from app.domain.models import User
from app.security.auth import authenticate_user, create_session, delete_session, get_valid_session
from app.services.audit import log_audit

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=UserResponse)
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> User:
    user = authenticate_user(db, payload.email, payload.password)
    if user is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    session = create_session(db, user)
    log_audit(
        db,
        actor=user,
        action=AuditAction.LOGIN,
        entity_type="User",
        entity_id=user.id,
    )
    db.commit()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=str(session.id),
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.session_max_age_seconds,
        path="/",
    )
    return user


@router.post("/logout")
def logout(
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    session_id: str | None = Cookie(default=None, alias=settings.session_cookie_name),
) -> dict[str, str]:
    if session_id:
        session = get_valid_session(db, session_id)
        if session:
            log_audit(
                db,
                actor=current_user,
                action=AuditAction.LOGOUT,
                entity_type="User",
                entity_id=current_user.id,
            )
            delete_session(db, session)
    response.delete_cookie(key=settings.session_cookie_name, path="/")
    return {"status": "ok"}


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.patch("/me", response_model=UserResponse)
def update_me(
    payload: UpdateProfileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    old_tz = current_user.timezone
    if payload.timezone is not None:
        current_user.timezone = payload.timezone
    log_audit(
        db,
        actor=current_user,
        action=AuditAction.UPDATE,
        entity_type="User",
        entity_id=current_user.id,
        old_value={"timezone": old_tz},
        new_value={"timezone": current_user.timezone},
    )
    db.commit()
    db.refresh(current_user)
    return current_user
