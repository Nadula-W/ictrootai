"""Explicit local-development recovery, never a web auth shortcut."""
import getpass
from sqlalchemy import select
from .config import settings
from .database import SessionLocal
from .models import User,Session
from .security import hash_password

def main():
    if settings.environment!='development':raise RuntimeError('Local recovery disabled outside development')
    password=getpass.getpass('New password for local demo accounts (10+ characters): ')
    if len(password)<10:raise ValueError('Password must have at least 10 characters')
    with SessionLocal() as db:
        for user in db.scalars(select(User).where(User.email.in_(['student@ictroot.local','teacher@ictroot.local','admin@ictroot.local']))):
            user.password=hash_password(password)
            for session in db.scalars(select(Session).where(Session.user_id==user.id)):db.delete(session)
        db.commit()
    print('Demo passwords updated; previous sessions revoked.')

if __name__=='__main__':main()
