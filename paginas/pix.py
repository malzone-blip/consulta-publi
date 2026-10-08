# -*- coding: utf-8 -*-
"""Pix: chaves no DICT, transacoes por perfil e estatisticas de fraude."""
from datetime import date

import pandas as pd
import streamlit as st

from core import auth, ui
from core.modulos import POR_CHAVE
from services import bcb, externas

CHAVE = "pix"


def _fins_de_mes(quantidade: int = 18):
    """Ultimos fechamentos mensais no formato AAAA-MM-DD, como a API espera."""
    hoje = date.today()
    ano, mes = hoje.year, hoje.month
    saida = []
    for _ in range(quantidade):
        mes -= 1
        if mes == 0:
            ano, mes = ano - 1, 12
        ultimo_dia = (pd.Timestamp(year=ano, month=mes, day=1)
                      + pd.offsets.MonthEnd(1)).date()
        saida.append(ultimo_dia.strftime("%Y-%m-%d"))
    return saida


def _meses(quantidade: int = 18):
    hoje = date.today()
    ano, mes = hoje.year, hoje.month
    saida = []
    for _ in range(quantidade):
        mes -= 1
        if mes == 0:
            ano, mes = ano - 1, 12
        saida.append("%d%02d" % (ano, mes))
    return saida


def render():
    auth.exigir(CHAVE)
    modulo = POR_CHAVE[CHAVE]
    forcar, atualizar = ui.controle_atualizacao(CHAVE)
    topo = st.container()  # cabecalho fica no topo, preenchido apos a consulta

    with st.spinner("Carregando panorama do Pix..."):
        usuarios, r_usuarios = bcb.pix_usuarios_dict(forcar)

    ui.cabecalho(modulo["titulo"], modulo["descricao"], r_usuarios, atualizar, destino=topo)

    if ui.verificar(r_usuarios, "usuarios do DICT") and not usuarios.empty:
        ultimo = usuarios.iloc[-1]
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Usuarios com chave",
                      ui.inteiro(ultimo["qtdUsuariosCadastradosDICTTotal"]),
                      help="Referencia: %s"
                           % ultimo["DataGraficosPix"].strftime("%d/%m/%Y"))
        with c2:
            st.metric("Pessoas fisicas", ui.inteiro(ultimo["qtdUsuariosPessoaFisica"]))
        with c3:
            st.metric("Pessoas juridicas",
                      ui.inteiro(ultimo["qtdUsuariosPessoaJuridica"]))
        with c4:
            if len(usuarios) > 12:
                doze_meses = usuarios.iloc[-13]
                crescimento = ((ultimo["qtdUsuariosCadastradosDICTTotal"]
                                / doze_meses["qtdUsuariosCadastradosDICTTotal"]) - 1) * 100
                st.metric("Crescimento em 12 meses", "%s%%" % ui.num(crescimento, 1))
        st.line_chart(
            usuarios.set_index("DataGraficosPix")[
                ["qtdUsuariosPessoaFisica", "qtdUsuariosPessoaJuridica"]
            ].rename(columns={"qtdUsuariosPessoaFisica": "Pessoas fisicas",
                              "qtdUsuariosPessoaJuridica": "Pessoas juridicas"}),
            height=250, color=["#2563EB", "#0EA5E9"])

    st.write("")
    aba_chaves, aba_transacoes, aba_fraude, aba_part = st.tabs(
        ["Chaves por instituicao", "Transacoes por perfil", "Fraudes e devolucoes",
         "Participantes"])

    with aba_chaves:
        _aba_chaves(forcar)
    with aba_transacoes:
        _aba_transacoes(forcar)
    with aba_fraude:
        _aba_fraudes(forcar)
    with aba_part:
        _aba_participantes(forcar)


def _aba_chaves(forcar):
    datas = _fins_de_mes()
    data_ref = st.selectbox("Data de referencia", datas,
                            format_func=lambda d: "%s/%s" % (d[5:7], d[:4]),
                            key="pix_data_chaves")
    with st.spinner("Carregando chaves cadastradas..."):
        df, resp = bcb.pix_chaves(data_ref, forcar)
    if not ui.verificar(resp, "chaves Pix"):
        return
    if df.empty:
        ui.vazio("Sem dados para essa data. Escolha um mes anterior.")
        return

    st.caption(resp.selo())
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Total de chaves", ui.inteiro(df["qtdChaves"].sum()))
    with c2:
        st.metric("Instituicoes com chaves", ui.inteiro(df["ISPB"].nunique()))
    with c3:
        pf = df[df["NaturezaUsuario"] == "PF"]["qtdChaves"].sum()
        st.metric("Participacao de PF",
                  "%s%%" % ui.num(pf / max(df["qtdChaves"].sum(), 1) * 100, 1))

    esq, dir_ = st.columns(2)
    with esq:
        st.markdown("##### Chaves por tipo")
        st.bar_chart(df.groupby("TipoChave")["qtdChaves"].sum().sort_values(),
                     height=260, horizontal=True, color="#2563EB")
    with dir_:
        st.markdown("##### Instituicoes com mais chaves")
        top = df.groupby("Nome")["qtdChaves"].sum().sort_values().tail(12)
        st.bar_chart(top, height=260, horizontal=True, color="#0EA5E9")

    exibir = (df.rename(columns={"Nome": "Instituicao", "TipoChave": "Tipo de chave",
                                 "NaturezaUsuario": "Natureza",
                                 "qtdChaves": "Quantidade de chaves"})
              .sort_values("Quantidade de chaves", ascending=False))
    ui.tabela(exibir, "pix_chaves_%s" % data_ref, altura=400)


def _aba_transacoes(forcar):
    c1, c2 = st.columns([0.5, 0.5])
    with c1:
        anomes = st.selectbox("Mes de referencia", _meses(),
                              format_func=lambda m: "%s/%s" % (m[4:], m[:4]),
                              key="pix_mes_transacoes")
    with c2:
        limite = st.select_slider("Volume de linhas", [2000, 5000, 20000, 50000],
                                  value=5000,
                                  help="A base cruza pagador x recebedor x regiao x "
                                       "faixa etaria e e grande. Comece pequeno.")
    with st.spinner("Carregando transacoes..."):
        df, resp = bcb.pix_transacoes(anomes, limite, forcar)
    if not ui.verificar(resp, "transacoes Pix"):
        return
    if df.empty:
        ui.vazio("Sem dados para esse mes. Escolha um mes anterior.")
        return

    st.caption(resp.selo())
    a, b, c = st.columns(3)
    with a:
        st.metric("Transacoes na amostra", ui.inteiro(df["QUANTIDADE"].sum()))
    with b:
        st.metric("Valor na amostra", ui.moeda(df["VALOR"].sum() / 1_000_000) + " mi")
    with c:
        st.metric("Ticket medio",
                  ui.moeda(df["VALOR"].sum() / max(df["QUANTIDADE"].sum(), 1)))

    dimensao = st.selectbox(
        "Agrupar por",
        ["NATUREZA", "PAG_REGIAO", "REC_REGIAO", "PAG_PFPJ", "REC_PFPJ",
         "PAG_IDADE", "REC_IDADE", "FORMAINICIACAO"],
        format_func=lambda c: {
            "NATUREZA": "Natureza da transacao", "PAG_REGIAO": "Regiao do pagador",
            "REC_REGIAO": "Regiao do recebedor", "PAG_PFPJ": "Pagador PF/PJ",
            "REC_PFPJ": "Recebedor PF/PJ", "PAG_IDADE": "Faixa etaria do pagador",
            "REC_IDADE": "Faixa etaria do recebedor",
            "FORMAINICIACAO": "Forma de iniciacao"}[c],
    )
    agrupado = (df.groupby(dimensao)[["QUANTIDADE", "VALOR"]].sum()
                .sort_values("QUANTIDADE", ascending=False))
    st.bar_chart(agrupado["QUANTIDADE"], height=280, color="#2563EB")
    ui.tabela(agrupado.reset_index().rename(
        columns={dimensao: "Categoria", "QUANTIDADE": "Quantidade", "VALOR": "Valor"}),
        "pix_transacoes_%s" % anomes, altura=320)


def _aba_fraudes(forcar):
    anos = [str(a) for a in range(date.today().year, date.today().year - 5, -1)]
    ano = st.selectbox("Ano", anos, index=1, key="pix_ano_fraude",
                       help="Esta base e anual: o parametro da API e o ano, nao o mes.")
    with st.spinner("Carregando estatisticas de fraude..."):
        df, resp = bcb.pix_fraudes(ano, forcar)
    if not ui.verificar(resp, "estatisticas de fraude"):
        return
    if df.empty:
        ui.vazio("Sem dados publicados para %s. Tente o ano anterior." % ano)
        return

    st.caption(resp.selo())
    ultimo = df.sort_values("AnoMes").iloc[-1]
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Pix contestados", ui.inteiro(ultimo.get("QtdePixcontestados")),
                  help="Mes de referencia: %s" % ultimo.get("AnoMes"))
    with c2:
        st.metric("Contestacoes aceitas",
                  ui.inteiro(ultimo.get("Qtdecontestacoesaceitas")))
    with c3:
        st.metric("Usuarios com marcacao de fraude",
                  ui.inteiro(ultimo.get("QtdeUsuarioscommarcacoesdefraude")))
    with c4:
        st.metric("Percentual devolvido",
                  "%s%%" % ui.num(ultimo.get("PercentualdeDevolucao"), 2))

    serie = df.sort_values("AnoMes").copy()
    serie["Mes"] = serie["AnoMes"].astype(str)
    st.markdown("##### Contestacoes ao longo do ano")
    st.bar_chart(serie.set_index("Mes")["QtdePixcontestados"], height=260,
                 color="#DC2626")

    ui.tabela(df, "pix_fraudes_%s" % ano, altura=340)
    ui.nota(
        "MED e o Mecanismo Especial de Devolucao: permite ao banco devolver "
        "recursos de um Pix reconhecido como fraude. Os numeros aqui sao agregados "
        "de todo o sistema, publicados pelo Banco Central."
    )


def _aba_participantes(forcar):
    with st.spinner("Carregando participantes do Pix..."):
        df, resp = externas.participantes_pix(forcar)
    if not ui.verificar(resp, "participantes do Pix"):
        return
    if df.empty:
        ui.vazio("Sem dados de participantes.")
        return
    st.caption(resp.selo())
    busca = st.text_input("Buscar participante", placeholder="Nome ou ISPB",
                          key="busca_part_pix")
    filtrado = df
    if busca:
        alvo = busca.strip().upper()
        filtrado = df[
            df["nome"].astype(str).str.upper().str.contains(alvo, na=False)
            | df["ispb"].astype(str).str.contains(alvo, na=False)
        ]
    st.metric("Participantes", ui.inteiro(len(filtrado)))
    ui.tabela(filtrado.rename(columns={
        "ispb": "ISPB", "nome": "Nome", "nome_reduzido": "Nome reduzido",
        "modalidade_participacao": "Modalidade",
        "tipo_participacao": "Tipo", "inicio_operacao": "Inicio de operacao"}),
        "pix_participantes", altura=400)
