# -*- coding: utf-8 -*-
"""Autenticacao, sessao e controle de acesso."""
import streamlit as st

from core import audit, db
from core.config import (APP_NOME, APP_SUBTITULO, BLOQUEIO_MINUTOS,
                         MAX_TENTATIVAS_LOGIN, SENHA_PADRAO)
from core.security import validar_forca, verificar_senha

CHAVE_SESSAO = "ip_usuario_id"


def _para_dict(linha) -> dict:
    return {
        "id": linha["id"],
        "usuario": linha["usuario"],
        "nome": linha["nome"],
        "email": linha["email"],
        "setor": linha["setor"],
        "is_admin": bool(linha["is_admin"]),
        "deve_trocar_senha": bool(linha["deve_trocar_senha"]),
        "ativo": bool(linha["ativo"]),
    }


def usuario_atual():
    """Usuario logado, relido do banco a cada execucao.

    A releitura garante que revogar permissao ou desativar um usuario tem
    efeito imediato, sem esperar ele deslogar.
    """
    uid = st.session_state.get(CHAVE_SESSAO)
    if not uid:
        return None
    linha = db.buscar_usuario_id(uid)
    if not linha or not linha["ativo"]:
        st.session_state.pop(CHAVE_SESSAO, None)
        return None
    return _para_dict(linha)


def permissoes():
    u = usuario_atual()
    if not u:
        return set()
    if u["is_admin"]:
        from core.modulos import MODULOS
        return {m["chave"] for m in MODULOS}
    return db.permissoes_do_usuario(u["id"])


def pode(chave: str) -> bool:
    return chave in permissoes()


def exigir(chave: str) -> None:
    """Guarda de pagina: interrompe a renderizacao se faltar permissao."""
    if not pode(chave):
        st.error("Voce nao tem permissao para acessar este modulo.",
                 icon=":material/lock:")
        st.stop()


def sair() -> None:
    u = usuario_atual()
    if u:
        audit.registrar(u["usuario"], "LOGOUT", "Encerrou a sessao.")
    st.session_state.pop(CHAVE_SESSAO, None)
    st.rerun()


# --------------------------------------------------------------------------
# Telas
# --------------------------------------------------------------------------
def tela_login() -> None:
    _, meio, _ = st.columns([1, 1.05, 1])
    with meio:
        st.markdown(
            '<div class="ip-login-marca"><div class="icone">IP</div>'
            '<h2>%s</h2><p>%s</p></div>' % (APP_NOME, APP_SUBTITULO),
            unsafe_allow_html=True,
        )
        with st.form("form_login", border=True):
            login = st.text_input("Usuario", placeholder="seu.usuario",
                                  autocomplete="username")
            senha = st.text_input("Senha", type="password", placeholder="Sua senha",
                                  autocomplete="current-password")
            entrar = st.form_submit_button("Entrar", use_container_width=True,
                                           type="primary")

        if entrar:
            _tentar_login(login.strip(), senha)

        st.caption(
            "Primeiro acesso: use a senha padrao fornecida pelo administrador. "
            "O sistema pedira a troca imediatamente."
        )


def _tentar_login(login: str, senha: str) -> None:
    if not login or not senha:
        st.error("Informe usuario e senha.", icon=":material/error:")
        return

    linha = db.buscar_usuario(login)
    if not linha:
        audit.registrar(login, "LOGIN_FALHA", "Usuario inexistente.")
        st.error("Usuario ou senha invalidos.", icon=":material/error:")
        return

    if not linha["ativo"]:
        audit.registrar(login, "LOGIN_BLOQUEADO", "Usuario inativo.")
        st.error("Este usuario esta inativo. Procure o administrador.",
                 icon=":material/block:")
        return

    if db.esta_bloqueado(linha):
        minutos = db.minutos_restantes_bloqueio(linha)
        audit.registrar(login, "LOGIN_BLOQUEADO",
                        "Tentativa durante bloqueio temporario.")
        st.error(
            "Acesso bloqueado por excesso de tentativas. Tente novamente em %d minuto(s)."
            % minutos, icon=":material/lock_clock:")
        return

    if not verificar_senha(senha, linha["senha_hash"], linha["salt"], linha["iteracoes"]):
        db.registrar_falha_login(linha["id"], MAX_TENTATIVAS_LOGIN, BLOQUEIO_MINUTOS)
        audit.registrar(login, "LOGIN_FALHA", "Senha incorreta.")
        st.error("Usuario ou senha invalidos.", icon=":material/error:")
        return

    db.registrar_login_ok(linha["id"])
    audit.registrar(linha["usuario"], "LOGIN", "Acesso concedido.")
    st.session_state[CHAVE_SESSAO] = linha["id"]
    st.rerun()


def tela_trocar_senha_obrigatoria() -> None:
    """Bloqueia o sistema ate o usuario sair da senha padrao."""
    u = usuario_atual()
    _, meio, _ = st.columns([1, 1.05, 1])
    with meio:
        st.markdown(
            '<div class="ip-login-marca"><div class="icone">IP</div>'
            '<h2>Defina sua senha</h2>'
            '<p>Este e o seu primeiro acesso, %s. Por seguranca, troque a senha '
            'padrao antes de continuar.</p></div>' % u["nome"].split()[0],
            unsafe_allow_html=True,
        )
        with st.form("form_troca", border=True):
            atual = st.text_input("Senha atual", type="password",
                                  placeholder="A senha que voce recebeu")
            nova = st.text_input("Nova senha", type="password",
                                 help="Minimo de 8 caracteres, com letras e numeros.")
            confirma = st.text_input("Confirme a nova senha", type="password")
            salvar = st.form_submit_button("Salvar e entrar", use_container_width=True,
                                           type="primary")

        if salvar:
            linha = db.buscar_usuario_id(u["id"])
            if not verificar_senha(atual, linha["senha_hash"], linha["salt"],
                                   linha["iteracoes"]):
                st.error("A senha atual esta incorreta.", icon=":material/error:")
            elif nova != confirma:
                st.error("A confirmacao nao confere com a nova senha.",
                         icon=":material/error:")
            else:
                valida, motivo = validar_forca(nova)
                if not valida:
                    st.error(motivo, icon=":material/error:")
                else:
                    db.gravar_nova_senha(u["id"], nova)
                    audit.registrar(u["usuario"], "SENHA_ALTERADA",
                                    "Troca obrigatoria no primeiro acesso.")
                    st.success("Senha atualizada. Redirecionando...",
                               icon=":material/check_circle:")
                    st.rerun()

        if st.button("Sair", use_container_width=True):
            sair()


def bloco_trocar_senha() -> None:
    """Troca voluntaria de senha, exibida na barra lateral."""
    u = usuario_atual()
    with st.sidebar.expander("Alterar minha senha", icon=":material/key:"):
        with st.form("form_troca_voluntaria", border=False):
            atual = st.text_input("Senha atual", type="password")
            nova = st.text_input("Nova senha", type="password")
            confirma = st.text_input("Confirmar", type="password")
            if st.form_submit_button("Alterar", use_container_width=True):
                linha = db.buscar_usuario_id(u["id"])
                if not verificar_senha(atual, linha["senha_hash"], linha["salt"],
                                       linha["iteracoes"]):
                    st.error("Senha atual incorreta.")
                elif nova != confirma:
                    st.error("A confirmacao nao confere.")
                else:
                    valida, motivo = validar_forca(nova)
                    if not valida:
                        st.error(motivo)
                    else:
                        db.gravar_nova_senha(u["id"], nova)
                        audit.registrar(u["usuario"], "SENHA_ALTERADA",
                                        "Alteracao voluntaria.")
                        st.success("Senha alterada.")


def aviso_senha_padrao_admin() -> None:
    """Alerta o administrador se algum usuario ainda esta na senha padrao."""
    pendentes = [u for u in db.listar_usuarios() if u["deve_trocar_senha"] and u["ativo"]]
    if pendentes:
        nomes = ", ".join(u["usuario"] for u in pendentes[:6])
        extra = " e mais %d" % (len(pendentes) - 6) if len(pendentes) > 6 else ""
        st.info(
            "%d usuario(s) ainda estao com a senha padrao '%s': %s%s."
            % (len(pendentes), SENHA_PADRAO, nomes, extra),
            icon=":material/info:",
        )
