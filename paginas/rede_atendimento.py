# -*- coding: utf-8 -*-
"""Rede fisica de atendimento: agencias e postos."""
import streamlit as st

from core import auth, ui
from core.modulos import POR_CHAVE
from services import bcb

CHAVE = "rede_atendimento"

UFS = ["AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS",
       "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC",
       "SE", "SP", "TO"]


def render():
    auth.exigir(CHAVE)
    modulo = POR_CHAVE[CHAVE]
    forcar, atualizar = ui.controle_atualizacao(CHAVE)
    topo = st.container()  # cabecalho fica no topo, preenchido apos a consulta

    f1, f2 = st.columns([0.28, 0.72])
    with f1:
        uf = st.selectbox("UF", UFS, index=UFS.index("SP"),
                          help="A consulta e feita por UF para manter a resposta rapida.")
    with f2:
        busca = st.text_input("Filtrar por instituicao ou municipio",
                              placeholder="Ex.: CAIXA, BRADESCO, CAMPINAS")

    aba_ag, aba_pa = st.tabs(["Agencias", "Postos de atendimento"])

    LIMITE = 30000
    with aba_ag:
        with st.spinner("Carregando agencias de %s..." % uf):
            df, resp = bcb.agencias(uf, LIMITE, forcar)
        ui.cabecalho(modulo["titulo"], modulo["descricao"], resp, atualizar, destino=topo)
        if ui.verificar(resp, "agencias"):
            ui.aviso_truncado(len(df), LIMITE, "Use o filtro para reduzir o conjunto.")
            _mostrar_agencias(df, busca, uf)

    with aba_pa:
        with st.spinner("Carregando postos de %s..." % uf):
            dfp, respp = bcb.postos_atendimento(uf, LIMITE, forcar)
        if ui.verificar(respp, "postos de atendimento"):
            ui.aviso_truncado(len(dfp), LIMITE, "Use o filtro para reduzir o conjunto.")
            _mostrar_postos(dfp, busca, uf)


def _aplicar_busca(df, busca, colunas):
    if not busca:
        return df
    alvo = busca.strip().upper()
    mascara = None
    for col in colunas:
        if col in df.columns:
            atual = df[col].astype(str).str.upper().str.contains(alvo, na=False)
            mascara = atual if mascara is None else (mascara | atual)
    return df[mascara] if mascara is not None else df


def _mostrar_agencias(df, busca, uf):
    if df.empty:
        ui.vazio("Nenhuma agencia retornada para %s." % uf)
        return
    filtrado = _aplicar_busca(df, busca, ["NomeIf", "Municipio", "NomeAgencia"])

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Agencias", ui.inteiro(len(filtrado)))
    with c2:
        st.metric("Instituicoes", ui.inteiro(filtrado["NomeIf"].nunique()))
    with c3:
        st.metric("Municipios atendidos", ui.inteiro(filtrado["Municipio"].nunique()))

    st.write("")
    esq, dir_ = st.columns([0.5, 0.5])
    with esq:
        st.markdown("##### Instituicoes com mais agencias")
        top = filtrado["NomeIf"].value_counts().head(12)
        st.bar_chart(top, height=300, horizontal=True, color="#2563EB")
    with dir_:
        st.markdown("##### Municipios com mais agencias")
        top_mun = filtrado["Municipio"].value_counts().head(12)
        st.bar_chart(top_mun, height=300, horizontal=True, color="#0EA5E9")

    exibir = filtrado.rename(columns={
        "NomeIf": "Instituicao", "NomeAgencia": "Agencia", "CodigoCompe": "COMPE",
        "Municipio": "Municipio", "Endereco": "Endereco", "Bairro": "Bairro",
        "Cep": "CEP", "Telefone": "Telefone", "DataInicio": "Inicio",
        "Segmento": "Segmento"})
    ordem = [c for c in ("Instituicao", "Agencia", "COMPE", "Municipio", "UF",
                         "Endereco", "Bairro", "CEP", "DDD", "Telefone", "Inicio")
             if c in exibir.columns]
    ui.tabela(exibir[ordem] if ordem else exibir, "agencias_%s" % uf, altura=430)


def _mostrar_postos(df, busca, uf):
    if df.empty:
        ui.vazio("Nenhum posto retornado para %s." % uf)
        return
    filtrado = _aplicar_busca(df, busca, [c for c in df.columns
                                          if df[c].dtype == object])
    st.metric("Postos de atendimento", ui.inteiro(len(filtrado)))
    ui.tabela(filtrado, "postos_%s" % uf, altura=430)
    ui.nota(
        "Postos de atendimento incluem PAs, PAEs e postos avancados - pontos que "
        "nao sao agencia plena mas prestam servico bancario presencial."
    )
