# -*- coding: utf-8 -*-
"""Registro de auditoria das acoes do sistema."""
from core.db import agora, conexao


def registrar(usuario: str, acao: str, detalhe: str = "") -> None:
    """Grava um evento. Nunca levanta excecao para nao derrubar a operacao."""
    try:
        with conexao() as con:
            con.execute(
                "INSERT INTO auditoria (quando, usuario, acao, detalhe) VALUES (?,?,?,?)",
                (agora(), usuario or "-", acao, (detalhe or "")[:2000]),
            )
    except Exception:
        pass


def listar(limite: int = 500, filtro_usuario: str = "", filtro_acao: str = ""):
    sql = "SELECT quando, usuario, acao, detalhe FROM auditoria WHERE 1=1"
    params: list = []
    if filtro_usuario:
        sql += " AND usuario LIKE ?"
        params.append("%" + filtro_usuario + "%")
    if filtro_acao:
        sql += " AND acao = ?"
        params.append(filtro_acao)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(int(limite))
    with conexao() as con:
        return con.execute(sql, params).fetchall()


def acoes_distintas():
    with conexao() as con:
        return [
            r["acao"] for r in con.execute("SELECT DISTINCT acao FROM auditoria ORDER BY acao")
        ]
