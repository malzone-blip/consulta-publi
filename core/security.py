# -*- coding: utf-8 -*-
"""Hash de senhas com PBKDF2-HMAC-SHA256 (biblioteca padrao, sem compilacao)."""
import hashlib
import os
import re
import secrets

from core.config import PBKDF2_ITERACOES, SENHA_MIN_TAMANHO, SENHA_PADRAO


def gerar_salt() -> str:
    return secrets.token_hex(16)


def hash_senha(senha: str, salt: str, iteracoes: int = PBKDF2_ITERACOES) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", senha.encode("utf-8"), bytes.fromhex(salt), iteracoes
    ).hex()


def criar_credencial(senha: str) -> tuple[str, str, int]:
    """Devolve (hash, salt, iteracoes) para gravar no banco."""
    salt = gerar_salt()
    return hash_senha(senha, salt), salt, PBKDF2_ITERACOES


def verificar_senha(senha: str, hash_guardado: str, salt: str, iteracoes: int) -> bool:
    calculado = hash_senha(senha, salt, iteracoes)
    return secrets.compare_digest(calculado, hash_guardado)


def validar_forca(senha: str) -> tuple[bool, str]:
    """Regras minimas para a senha escolhida pelo proprio usuario."""
    if len(senha or "") < SENHA_MIN_TAMANHO:
        return False, "A senha deve ter no minimo %d caracteres." % SENHA_MIN_TAMANHO
    if senha == SENHA_PADRAO:
        return False, "Escolha uma senha diferente da senha padrao do sistema."
    if not re.search(r"[A-Za-z]", senha):
        return False, "A senha deve conter ao menos uma letra."
    if not re.search(r"\d", senha):
        return False, "A senha deve conter ao menos um numero."
    if senha.lower() in {"12345678", "senha123", "password", "administrador"}:
        return False, "Senha muito comum. Escolha outra."
    return True, ""
