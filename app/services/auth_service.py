from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


PBKDF2_ITERATIONS = 600_000


@dataclass(slots=True)
class RegistrationResult:
    ok: bool
    error: Optional[str] = None


@dataclass(slots=True)
class AuthResult:
    ok: bool
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    error: Optional[str] = None


class AuthService:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        with self._connect() as conn:
            cols = conn.execute('PRAGMA table_info(users)').fetchall()
            if not cols:
                return
            col_names = {str(col['name']) for col in cols}
            if 'avatar_path' not in col_names:
                conn.execute('ALTER TABLE users ADD COLUMN avatar_path TEXT')
            if 'had_projects' not in col_names:
                conn.execute('ALTER TABLE users ADD COLUMN had_projects INTEGER NOT NULL DEFAULT 0')
            conn.commit()

    def email_exists(self, email: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM users WHERE lower(email) = lower(?) LIMIT 1",
                (email.strip(),),
            ).fetchone()
            return row is not None

    def get_user_by_email(self, email: str) -> Optional[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(
                "SELECT id, name, email, password_hash, is_active, avatar_path, had_projects FROM users WHERE lower(email) = lower(?) LIMIT 1",
                (email.strip(),),
            ).fetchone()

    def get_user_by_id(self, user_id: int) -> Optional[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(
                "SELECT id, name, email, password_hash, is_active, avatar_path, had_projects FROM users WHERE id = ? LIMIT 1",
                (user_id,),
            ).fetchone()

    def update_user_profile(self, user_id: int, *, name: str, avatar_path: str | None) -> None:
        normalized_name = (name or "").strip()
        if len(normalized_name) < 2:
            raise ValueError("Имя должно содержать хотя бы 2 символа.")
        with self._connect() as conn:
            conn.execute(
                "UPDATE users SET name = ?, avatar_path = ? WHERE id = ?",
                (normalized_name, avatar_path, user_id),
            )
            conn.commit()

    def change_password(self, user_id: int, *, new_password: str, current_password: str | None = None) -> None:
        row = self.get_user_by_id(user_id)
        if row is None:
            raise ValueError("Пользователь не найден.")
        if current_password is not None and not self.verify_password(current_password or "", str(row["password_hash"])):
            raise ValueError("Текущий пароль введен неверно.")
        if len((new_password or "").strip()) < 8:
            raise ValueError("Новый пароль должен содержать минимум 8 символов.")
        new_hash = self.hash_password(new_password)
        with self._connect() as conn:
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (new_hash, user_id),
            )
            conn.commit()

    def hash_password(self, password: str) -> str:
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, PBKDF2_ITERATIONS)
        return f'pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}'

    def verify_password(self, password: str, encoded_hash: str) -> bool:
        try:
            algorithm, iterations_str, salt_hex, digest_hex = encoded_hash.split('$', 3)
            if algorithm != 'pbkdf2_sha256':
                return False
            iterations = int(iterations_str)
        except ValueError:
            return False

        calculated = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            bytes.fromhex(salt_hex),
            iterations,
        ).hex()
        return hmac.compare_digest(calculated, digest_hex)

    def register_user(self, name: str, email: str, password: str) -> RegistrationResult:
        normalized_name = name.strip()
        normalized_email = email.strip().lower()

        if len(normalized_name) < 2:
            return RegistrationResult(ok=False, error='Имя должно содержать хотя бы 2 символа.')

        if '@' not in normalized_email or '.' not in normalized_email.split('@')[-1]:
            return RegistrationResult(ok=False, error='Введите корректный email.')

        if len(password) < 8:
            return RegistrationResult(ok=False, error='Пароль должен содержать минимум 8 символов.')

        if self.email_exists(normalized_email):
            return RegistrationResult(ok=False, error='Пользователь с таким email уже зарегистрирован.')

        password_hash = self.hash_password(password)
        created_at = datetime.now(timezone.utc).isoformat()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO users (name, email, password_hash, auth_provider, created_at)
                VALUES (?, ?, ?, 'local', ?)
                """,
                (normalized_name, normalized_email, password_hash, created_at),
            )
            conn.commit()

        return RegistrationResult(ok=True)

    def authenticate_user(self, email: str, password: str) -> AuthResult:
        normalized_email = email.strip().lower()

        if '@' not in normalized_email or len(password) < 1:
            return AuthResult(ok=False, error='Введите email и пароль.')

        row = self.get_user_by_email(normalized_email)
        if row is None:
            return AuthResult(ok=False, error='Пользователь с таким email не найден.')

        if not row['is_active']:
            return AuthResult(ok=False, error='Аккаунт деактивирован.')

        if not self.verify_password(password, row['password_hash']):
            return AuthResult(ok=False, error='Неверный пароль.')

        return AuthResult(
            ok=True,
            user_id=int(row['id']),
            user_name=str(row['name']),
            user_email=str(row['email']),
        )
