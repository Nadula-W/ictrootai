import hashlib
import secrets
from datetime import datetime, timezone
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session as DBSession
from .database import get_db
from .models import User, Session

def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    return salt + ':' + hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex()

def verify_password(password, stored):
    return secrets.compare_digest(hash_password(password, stored.split(':')[0]), stored)

def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()

def current_user(request: Request, db: DBSession = Depends(get_db)):
    token = request.cookies.get('ictroot_session', '')
    session = db.get(Session, digest(token))
    if not session or session.expires.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(401, 'Please sign in')
    user = db.get(User, session.user_id)
    if not user:
        raise HTTPException(401, 'Session invalid')
    return user

def staff(user=Depends(current_user)):
    if user.role not in ('teacher', 'admin'):
        raise HTTPException(403, 'Teacher access required')
    return user

def admin(user=Depends(current_user)):
    if user.role != 'admin':
        raise HTTPException(403, 'Administrator access required')
    return user
