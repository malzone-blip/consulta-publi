# -*- coding: utf-8 -*-
"""Camada de banco (SQLite em modo WAL, seguro para multiplos usuarios)."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta

from core.config import BANCO, SENHA_PADRAO
from core.security import criar_credencial

ESQUEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario           TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    nome              TEXT    NOT NULL,
    email             TEXT,
    setor             TEXT,
    senha_hash        TEXT    NOT NULL,
    salt              TEXT    NOT NULL,
    iteracoes         INTEGER NOT NULL,
    is_admin          INTEGER NOT NULL DEFAULT 0,
    deve_trocar_senha INTEGER NOT NULL DEFAULT 1,
    ativo             INTEGER NOT NULL DEFAULT 1,
    criado_em         TEXT    NOT NULL,
    criado_por        TEXT,
    ultimo_login      TEXT,
    tentativas_falhas INTEGER NOT NULL DEFAULT 0,
    bloqueado_ate     TEXT
);

CREATE TABLE IF NOT EXISTS permissoes (
    usuario_id INTEGER NOT NULL,
    modulo     TEXT    NOT NULL,
    PRIMARY KEY (usuario_id, modulo),
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS auditoria (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    quando  TEXT NOT NULL,
    usuario TEXT,
    acao    TEXT NOT NULL,
    detalhe TEXT
);

CREATE TABLE IF NOT EXISTS configuracoes (
    chave       TEXT PRIMARY KEY,
    valor       TEXT,
    atualizado  TEXT,
    atualizado_por TEXT
);

CREATE INDEX IF NOT EXISTS ix_auditoria_quando ON auditoria(quando DESC);
CREATE INDEX IF NOT EXISTS ix_permissoes_usuario ON permissoes(usuario_id);
"""


@contextmanager
def conexao():
    """Conexao curta por operacao: evita lock entre sessoes simultaneas."""
    con = sqlite3.connect(str(BANCO), timeout=20, check_same_thread=False)
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA busy_timeout=8000")
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def agora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def inicializar() -> None:
    """Cria o esquema e o administrador inicial na primeira execucao."""
    with conexao() as con:
        con.executescript(ESQUEMA)
        existe = con.execute("SELECT COUNT(*) AS n FROM usuarios").fetchone()["n"]
        if existe == 0:
            h, salt, it = criar_credencial(SENHA_PADRAO)
            con.execute(
                """INSERT INTO usuarios
                   (usuario, nome, email, setor, senha_hash, salt, iteracoes,
                    is_admin, deve_trocar_senha, ativo, criado_em, criado_por)
                   VALUES (?,?,?,?,?,?,?,1,1,1,?,?)""",
                ("admin", "Administrador do Sistema", "", "TI",
                 h, salt, it, agora(), "instalacao"),
            )
            con.execute(
                "INSERT INTO auditoria (quando, usuario, acao, detalhe) VALUES (?,?,?,?)",
                (agora(), "sistema", "INSTALACAO",
                 "Usuario 'admin' criado com a senha padrao; troca obrigatoria no 1o acesso."),
            )


# --- Consultas de usuario ---------------------------------------------------
def buscar_usuario(login: str):
    with conexao() as con:
        return con.execute(
            "SELECT * FROM usuarios WHERE usuario = ? COLLATE NOCASE", (login,)
        ).fetchone()


def buscar_usuario_id(uid: int):
    with conexao() as con:
        return con.execute("SELECT * FROM usuarios WHERE id = ?", (uid,)).fetchone()


def listar_usuarios():
    with conexao() as con:
        return con.execute(
            """SELECT u.*, (SELECT COUNT(*) FROM permissoes p WHERE p.usuario_id = u.id)
                      AS qtd_permissoes
               FROM usuarios u ORDER BY u.is_admin DESC, u.nome"""
        ).fetchall()


def criar_usuario(usuario, nome, email, setor, is_admin, modulos, criado_por):
    """Cria usuario com a senha padrao e troca obrigatoria no primeiro login."""
    h, salt, it = criar_credencial(SENHA_PADRAO)
    with conexao() as con:
        cur = con.execute(
            """INSERT INTO usuarios
               (usuario, nome, email, setor, senha_hash, salt, iteracoes,
                is_admin, deve_trocar_senha, ativo, criado_em, criado_por)
               VALUES (?,?,?,?,?,?,?,?,1,1,?,?)""",
            (usuario.strip(), nome.strip(), (email or "").strip(), (setor or "").strip(),
             h, salt, it, 1 if is_admin else 0, agora(), criado_por),
        )
        uid = cur.lastrowid
        for m in modulos or []:
            con.execute(
                "INSERT OR IGNORE INTO permissoes (usuario_id, modulo) VALUES (?,?)", (uid, m)
            )
        return uid


def atualizar_usuario(uid, nome, email, setor, is_admin, ativo, modulos):
    with conexao() as con:
        con.execute(
            "UPDATE usuarios SET nome=?, email=?, setor=?, is_admin=?, ativo=? WHERE id=?",
            (nome.strip(), (email or "").strip(), (setor or "").strip(),
             1 if is_admin else 0, 1 if ativo else 0, uid),
        )
        con.execute("DELETE FROM permissoes WHERE usuario_id=?", (uid,))
        for m in modulos or []:
            con.execute(
                "INSERT OR IGNORE INTO permissoes (usuario_id, modulo) VALUES (?,?)", (uid, m)
            )


def excluir_usuario(uid: int) -> None:
    with conexao() as con:
        con.execute("DELETE FROM permissoes WHERE usuario_id=?", (uid,))
        con.execute("DELETE FROM usuarios WHERE id=?", (uid,))


def contar_admins_ativos() -> int:
    with conexao() as con:
        return con.execute(
            "SELECT COUNT(*) AS n FROM usuarios WHERE is_admin=1 AND ativo=1"
        ).fetchone()["n"]


def redefinir_para_senha_padrao(uid: int) -> None:
    h, salt, it = criar_credencial(SENHA_PADRAO)
    with conexao() as con:
        con.execute(
            """UPDATE usuarios SET senha_hash=?, salt=?, iteracoes=?, deve_trocar_senha=1,
                                   tentativas_falhas=0, bloqueado_ate=NULL
               WHERE id=?""",
            (h, salt, it, uid),
        )


def gravar_nova_senha(uid: int, senha: str) -> None:
    h, salt, it = criar_credencial(senha)
    with conexao() as con:
        con.execute(
            """UPDATE usuarios SET senha_hash=?, salt=?, iteracoes=?, deve_trocar_senha=0,
                                   tentativas_falhas=0, bloqueado_ate=NULL
               WHERE id=?""",
            (h, salt, it, uid),
        )


def permissoes_do_usuario(uid: int) -> set:
    with conexao() as con:
        return {
            r["modulo"]
            for r in con.execute("SELECT modulo FROM permissoes WHERE usuario_id=?", (uid,))
        }


# --- Controle de tentativas de login ---------------------------------------
def registrar_falha_login(uid: int, maximo: int, minutos: int) -> None:
    with conexao() as con:
        row = con.execute(
            "SELECT tentativas_falhas FROM usuarios WHERE id=?", (uid,)
        ).fetchone()
        n = (row["tentativas_falhas"] or 0) + 1
        bloqueio = None
        if n >= maximo:
            bloqueio = (datetime.now() + timedelta(minutes=minutos)).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            n = 0
        con.execute(
            "UPDATE usuarios SET tentativas_falhas=?, bloqueado_ate=? WHERE id=?",
            (n, bloqueio, uid),
        )


def registrar_login_ok(uid: int) -> None:
    with conexao() as con:
        con.execute(
            """UPDATE usuarios SET ultimo_login=?, tentativas_falhas=0, bloqueado_ate=NULL
               WHERE id=?""",
            (agora(), uid),
        )


def esta_bloqueado(row) -> bool:
    if not row or not row["bloqueado_ate"]:
        return False
    try:
        return datetime.strptime(row["bloqueado_ate"], "%Y-%m-%d %H:%M:%S") > datetime.now()
    except (ValueError, TypeError):
        return False


# --- Configuracoes do sistema (chaves de API, parametros) -------------------
def obter_config(chave: str, padrao: str = "") -> str:
    """Le um parametro de configuracao gravado pela area administrativa."""
    try:
        with conexao() as con:
            linha = con.execute(
                "SELECT valor FROM configuracoes WHERE chave = ?", (chave,)
            ).fetchone()
        return (linha["valor"] if linha and linha["valor"] else padrao) or padrao
    except Exception:
        return padrao


def definir_config(chave: str, valor: str, por: str = "") -> None:
    with conexao() as con:
        con.execute(
            """INSERT INTO configuracoes (chave, valor, atualizado, atualizado_por)
               VALUES (?,?,?,?)
               ON CONFLICT(chave) DO UPDATE SET
                   valor = excluded.valor,
                   atualizado = excluded.atualizado,
                   atualizado_por = excluded.atualizado_por""",
            (chave, (valor or "").strip(), agora(), por),
        )


def remover_config(chave: str) -> None:
    with conexao() as con:
        con.execute("DELETE FROM configuracoes WHERE chave = ?", (chave,))


def listar_config():
    with conexao() as con:
        return con.execute(
            "SELECT chave, valor, atualizado, atualizado_por FROM configuracoes ORDER BY chave"
        ).fetchall()


def minutos_restantes_bloqueio(row) -> int:
    try:
        fim = datetime.strptime(row["bloqueado_ate"], "%Y-%m-%d %H:%M:%S")
        return max(1, int((fim - datetime.now()).total_seconds() // 60) + 1)
    except (ValueError, TypeError):
        return 0
