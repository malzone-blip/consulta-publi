# -*- coding: utf-8 -*-
"""Consultas rapidas do dia a dia: CNPJ, CEP, bancos e feriados."""
from datetime import date

import pandas as pd
import streamlit as st

from core import audit, auth, ui
from core.modulos import POR_CHAVE
from services import externas

CHAVE = "consultas"


def render():
    auth.exigir(CHAVE)
    modulo = POR_CHAVE[CHAVE]
    forcar, atualizar = ui.controle_atualizacao(CHAVE)
    topo = st.container()  # cabecalho fica no topo, preenchido apos a consulta

    ui.cabecalho(modulo["titulo"], modulo["descricao"], None, atualizar, destino=topo)

    aba_cnpj, aba_cep, aba_bancos, aba_feriados = st.tabs(
        ["CNPJ", "CEP", "Bancos", "Feriados"])

    with aba_cnpj:
        _aba_cnpj()
    with aba_cep:
        _aba_cep()
    with aba_bancos:
        _aba_bancos(forcar)
    with aba_feriados:
        _aba_feriados(forcar)


def _aba_cnpj():
    c1, c2 = st.columns([0.7, 0.3])
    with c1:
        entrada = st.text_input("CNPJ", placeholder="00.000.000/0000-00",
                                key="consulta_cnpj")
    with c2:
        st.write("")
        buscar = st.button("Consultar", use_container_width=True, type="primary",
                           key="btn_cnpj", icon=":material/search:")

    if buscar and entrada:
        with st.spinner("Consultando..."):
            dados, erro = externas.consultar_cnpj(entrada)
        audit.registrar(auth.usuario_atual()["usuario"], "CONSULTA_CNPJ",
                        "cnpj=%s" % entrada.strip()[:20])
        if erro:
            st.error(erro, icon=":material/error:")
            return
        st.success("Empresa localizada.", icon=":material/check_circle:")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Situacao cadastral",
                      str(dados.get("descricao_situacao_cadastral", "-")).title())
        with c2:
            st.metric("Porte", str(dados.get("porte", "-")).title())
        with c3:
            st.metric("Abertura", ui.data_br(dados.get("data_inicio_atividade")) or "-")

        st.markdown("**%s**" % (dados.get("razao_social") or "-"))
        if dados.get("nome_fantasia"):
            st.caption("Nome fantasia: %s" % dados["nome_fantasia"])

        detalhes = {
            "CNPJ": ui.cnpj_formatado(dados.get("cnpj")),
            "Natureza juridica": dados.get("natureza_juridica"),
            "Atividade principal": dados.get("cnae_fiscal_descricao"),
            "Capital social": ui.moeda(dados.get("capital_social") or 0),
            "Endereco": "%s, %s %s" % (dados.get("logradouro", ""),
                                       dados.get("numero", ""),
                                       dados.get("complemento", "") or ""),
            "Bairro": dados.get("bairro"),
            "Municipio / UF": "%s / %s" % (dados.get("municipio", ""),
                                           dados.get("uf", "")),
            "CEP": dados.get("cep"),
            "Telefone": dados.get("ddd_telefone_1"),
            "E-mail": dados.get("email"),
        }
        ui.tabela(pd.DataFrame({"Campo": list(detalhes.keys()),
                                "Valor": [str(v or "-") for v in detalhes.values()]}),
                  "cnpj_%s" % (dados.get("cnpj") or "consulta"), altura=380)

        socios = dados.get("qsa") or []
        if socios:
            st.markdown("##### Quadro societario")
            ui.tabela(pd.DataFrame(socios), "socios", altura=240)


def _aba_cep():
    c1, c2 = st.columns([0.7, 0.3])
    with c1:
        entrada = st.text_input("CEP", placeholder="00000-000", key="consulta_cep")
    with c2:
        st.write("")
        buscar = st.button("Consultar", use_container_width=True, type="primary",
                           key="btn_cep", icon=":material/search:")
    if buscar and entrada:
        with st.spinner("Consultando..."):
            dados, erro = externas.consultar_cep(entrada)
        if erro:
            st.error(erro, icon=":material/error:")
            return
        st.success("Endereco localizado.", icon=":material/check_circle:")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Cidade", dados.get("city", "-"))
        with c2:
            st.metric("Estado", dados.get("state", "-"))
        with c3:
            st.metric("Bairro", dados.get("neighborhood", "-") or "-")
        st.markdown("**%s**" % (dados.get("street") or "Logradouro nao informado"))
        st.caption("CEP %s - fonte: %s" % (dados.get("cep", "-"),
                                           dados.get("service", "-")))


def _aba_bancos(forcar):
    with st.spinner("Carregando bancos..."):
        df, resp = externas.bancos(forcar)
    if not ui.verificar(resp, "lista de bancos"):
        return
    if df.empty:
        ui.vazio("Sem dados de bancos.")
        return
    st.caption(resp.selo())
    busca = st.text_input("Buscar por nome, codigo COMPE ou ISPB",
                          placeholder="Ex.: 341, itau, 60701190", key="busca_banco")
    filtrado = df
    if busca:
        alvo = busca.strip().upper()
        filtrado = df[
            df["name"].astype(str).str.upper().str.contains(alvo, na=False)
            | df["fullName"].astype(str).str.upper().str.contains(alvo, na=False)
            | df["code"].astype(str).str.contains(alvo, na=False)
            | df["ispb"].astype(str).str.contains(alvo, na=False)
        ]
    ui.tabela(filtrado.rename(columns={
        "code": "COMPE", "name": "Nome curto", "fullName": "Razao social",
        "ispb": "ISPB"}), "bancos", altura=430)


def _aba_feriados(forcar):
    ano = st.selectbox("Ano", list(range(date.today().year - 1,
                                         date.today().year + 3)),
                       index=1, key="ano_feriados")
    with st.spinner("Carregando feriados..."):
        df, resp = externas.feriados(ano, forcar)
    if not ui.verificar(resp, "feriados nacionais"):
        return
    if df.empty:
        ui.vazio("Sem feriados retornados.")
        return
    st.caption(resp.selo())
    exibir = df.copy()
    exibir["date"] = pd.to_datetime(exibir["date"], errors="coerce")
    exibir["Dia da semana"] = exibir["date"].dt.day_name()
    exibir["date"] = exibir["date"].dt.strftime("%d/%m/%Y")
    ui.tabela(exibir.rename(columns={"date": "Data", "name": "Feriado",
                                     "type": "Tipo"}),
              "feriados_%d" % ano, altura=430)
    ui.nota(
        "Feriados nacionais definidos em lei federal. Feriados municipais e "
        "estaduais nao entram nesta lista e precisam ser conferidos localmente."
    )
