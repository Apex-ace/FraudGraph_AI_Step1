"""Small local-only authentication option for offline hackathon demos.

Passwords are PBKDF2-HMAC-SHA256 hashed; JWTs expire after 12 hours.
Not a replacement for a hardened public-facing identity service.
"""
from datetime import datetime, timedelta, timezone
from hashlib import pbkdf2_hmac
import hmac
import os
import secrets
from uuid import UUID

import jwt
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import backend_path, settings
from app.core.database import get_engine
from app.models.local_user import LocalUser

ITERATIONS = 600_000
ALGORITHM = "pbkdf2_sha256"
TOKEN_HOURS = 12


def _secret():
    path = backend_path(settings.local_auth_secret_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            out.write(secrets.token_hex(32))
    secret = path.read_text(encoding='utf-8').strip()
    if len(secret) < 32:
        raise RuntimeError("Local auth secret is missing or too short")
    return secret


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = pbkdf2_hmac('sha256', password.encode('utf-8'), salt, ITERATIONS)
    return f'{ALGORITHM}${ITERATIONS}${salt.hex()}${digest.hex()}'


def check_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt, expected = encoded.split('$')
        if algorithm != ALGORITHM or int(rounds) < 100000:
            return False
        calculated = pbkdf2_hmac('sha256', password.encode('utf-8'), bytes.fromhex(salt), int(rounds))
        return hmac.compare_digest(calculated, bytes.fromhex(expected))
    except (ValueError, TypeError):
        return False


def issue_token(user: LocalUser) -> dict:
    now = datetime.now(timezone.utc)
    token = jwt.encode({'sub': str(user.id), 'email': user.email,
                        'iss': 'fraudgraph-local', 'aud': 'fraudgraph-api',
                        'iat': now, 'exp': now + timedelta(hours=TOKEN_HOURS)},
                       _secret(), algorithm='HS256')
    return {'access_token': token, 'token_type': 'bearer',
            'user': {'id': str(user.id), 'email': user.email}}


def register_user(email: str, password: str) -> dict:
    clean = email.strip().lower()
    with Session(get_engine()) as db:
        if db.scalar(select(LocalUser.id).where(LocalUser.email == clean)):
            raise HTTPException(409, detail='This email is already registered locally')
        user = LocalUser(email=clean, password_hash=hash_password(password))
        db.add(user)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(409, detail='This email is already registered locally') from exc
        db.refresh(user)
        return issue_token(user)


def login_user(email: str, password: str) -> dict:
    with Session(get_engine()) as db:
        user = db.scalar(select(LocalUser).where(LocalUser.email == email.strip().lower()))
        if not user or not check_password(password, user.password_hash):
            raise HTTPException(401, detail='Invalid email or password')
        return issue_token(user)


def verify_local_token(token: str) -> dict:
    try:
        claims = jwt.decode(token, _secret(), algorithms=['HS256'],
                            issuer='fraudgraph-local', audience='fraudgraph-api',
                            options={'require': ['sub', 'iss', 'aud', 'exp', 'iat']})
        user_id = UUID(claims['sub'])
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise ValueError('Invalid or expired local access token') from exc
    with Session(get_engine()) as db:
        user = db.get(LocalUser, user_id)
        if not user:
            raise ValueError('Local account no longer exists')
        return {'id': str(user.id), 'email': user.email}
