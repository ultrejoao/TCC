"""Cria o primeiro usuario ADMIN.

"""

import argparse
import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.security import hash_password, password_issues  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models.user import User  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Cria o primeiro usuario ADMIN.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()

    email = args.email.strip().lower()

    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == email)):
            print(f"[erro] ja existe usuario com o e-mail {email}")
            return 1

        total = db.scalar(select(User).limit(1))
        if total is not None:
            print("[aviso] o banco ja possui usuarios. Prefira cadastrar novos")
            print("        usuarios pelo ADMIN existente, nao por este script.")
            if input("        continuar mesmo assim? [s/N] ").strip().lower() != "s":
                return 1

        senha = os.getenv("ADMIN_PASSWORD")
        if not senha:
            senha = getpass.getpass("Senha do ADMIN (min. 12 caracteres): ")
            if senha != getpass.getpass("Confirme a senha: "):
                print("[erro] as senhas nao conferem")
                return 1

        problemas = password_issues(senha)
        if problemas:
            print("[erro] senha fraca: " + "; ".join(problemas))
            return 1

        db.add(User(name=args.name.strip(), email=email,
                    password_hash=hash_password(senha), role="ADMIN", is_active=True))
        db.commit()

    print(f"[ok] ADMIN criado: {email}")
    print("     Guarde a senha: ela nao pode ser recuperada, apenas redefinida.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
