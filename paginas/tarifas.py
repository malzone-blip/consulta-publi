# -*- coding: utf-8 -*-
"""Tarifas bancarias: o que o mercado cobra e o que cada instituicao cobra."""
import streamlit as st

from core import auth, ui
from core.modulos import POR_CHAVE
from services import bcb

CHAVE = "tarifas"

PESSOA = {"F": "Pessoa fisica", "J": "Pessoa juridica"}


def render():
    auth.exigir(CHAVE)
    modulo = POR_CHAVE[CHAVE]
    forcar, atualizar = ui.controle_atualizacao(CHAVE)
    topo = st.container()  # cabecalho fica no topo, preenchido apos a consulta

    with st.spinner("Carregando grupos de instituicoes..."):
        grupos, r_grupos = bcb.tarifas_grupos(forcar)

    ui.cabecalho(modulo["titulo"], modulo["descricao"], r_grupos, atualizar, destino=topo)
    if not ui.verificar(r_grupos, "grupos de instituicoes"):
        return
    if grupos.empty:
        ui.vazio("A fonte nao retornou os grupos consolidados.")
        return

    mapa_grupos = {r["Codigo"]: r["Nome"] for _, r in grupos.iterrows()}

    aba_mercado, aba_instituicao = st.tabs(
        ["Referencia de mercado", "Tarifas de uma instituicao"])

    with aba_mercado:
        c1, c2 = st.columns(2)
        with c1:
            pessoa = st.radio("Perfil", list(PESSOA.keys()), horizontal=True,
                              format_func=lambda p: PESSOA[p], key="tar_pessoa_merc")
        with c2:
            grupo = st.selectbox("Grupo de instituicoes", list(mapa_grupos.keys()),
                                 format_func=lambda c: "%s - %s" % (c, mapa_grupos[c]),
                                 key="tar_grupo_merc")

        with st.spinner("Consultando valores praticados..."):
            df, resp = bcb.tarifas_valores_mercado(pessoa, grupo, forcar)
        if not ui.verificar(resp, "valores de servicos bancarios"):
            return
        if df.empty:
            ui.vazio("Sem tarifas publicadas para essa combinacao.")
        else:
            st.caption(resp.selo())
            st.metric("Servicos tarifados", ui.inteiro(len(df)))
            busca = st.text_input("Filtrar servico", placeholder="Ex.: TED, cartao, saque",
                                  key="tar_busca_merc")
            filtrado = df
            if busca:
                filtrado = df[df["NomeServico"].astype(str).str.upper().str.contains(
                    busca.strip().upper(), na=False)]
            exibir = filtrado.rename(columns={
                "CodigoServico": "Codigo", "NomeServico": "Servico",
                "ValorMinimo": "Minimo (R$)", "ValorMaximo": "Maximo (R$)",
                "ValorMedio": "Medio (R$)",
                "PeriodicidadeValorMinimo": "Periodicidade (min)",
                "PeriodicidadeValorMaximo": "Periodicidade (max)"})
            ui.tabela(exibir, "tarifas_mercado_%s_%s" % (pessoa, grupo), altura=430,
                      config={
                          "Minimo (R$)": st.column_config.NumberColumn(format="%.2f"),
                          "Maximo (R$)": st.column_config.NumberColumn(format="%.2f"),
                          "Medio (R$)": st.column_config.NumberColumn(format="%.2f"),
                      })
            ui.nota(
                "Os extremos desta tabela costumam ser distorcidos por tarifas de "
                "teto contratual (valores como 99.999,99). Para negociacao, o valor "
                "medio e a referencia util."
            )

    with aba_instituicao:
        c1, c2 = st.columns(2)
        with c1:
            pessoa_i = st.radio("Perfil", list(PESSOA.keys()), horizontal=True,
                                format_func=lambda p: PESSOA[p], key="tar_pessoa_inst")
        with c2:
            grupo_i = st.selectbox("Grupo", list(mapa_grupos.keys()),
                                   format_func=lambda c: "%s - %s" % (c, mapa_grupos[c]),
                                   key="tar_grupo_inst")

        with st.spinner("Carregando instituicoes do grupo..."):
            insts, r_insts = bcb.tarifas_instituicoes_do_grupo(grupo_i, forcar)
        if not ui.verificar(r_insts, "instituicoes do grupo"):
            return
        if insts.empty:
            ui.vazio("Nenhuma instituicao nesse grupo.")
            return

        mapa_inst = {r["Cnpj"]: r["Nome"] for _, r in insts.iterrows()}
        cnpj = st.selectbox("Instituicao", list(mapa_inst.keys()),
                            format_func=lambda c: mapa_inst[c], key="tar_inst")

        with st.spinner("Consultando tarifas da instituicao..."):
            df_i, resp_i = bcb.tarifas_da_instituicao(pessoa_i, cnpj, forcar)
        if not ui.verificar(resp_i, "tarifas da instituicao"):
            return
        if df_i.empty:
            ui.vazio("Essa instituicao nao possui tarifas publicadas para o perfil "
                     "selecionado.")
            return

        st.caption(resp_i.selo())
        c1, c2 = st.columns(2)
        with c1:
            st.metric("Servicos tarifados", ui.inteiro(len(df_i)))
        with c2:
            if "DataVigencia" in df_i:
                st.metric("Vigencia mais recente",
                          str(df_i["DataVigencia"].max())[:10])

        exibir = df_i.rename(columns={
            "CodigoServico": "Codigo", "Servico": "Servico", "Unidade": "Unidade",
            "DataVigencia": "Vigencia desde", "ValorMaximo": "Valor maximo (R$)",
            "TipoValor": "Tipo", "Periodicidade": "Periodicidade"})
        ui.tabela(exibir, "tarifas_%s_%s" % (cnpj, pessoa_i), altura=430, config={
            "Valor maximo (R$)": st.column_config.NumberColumn(format="%.2f")})
        ui.nota(
            "O valor publicado e o teto que a instituicao se comprometeu a cobrar "
            "junto ao Banco Central. Cobranca acima do declarado e irregular e pode "
            "ser objeto de reclamacao formal."
        )
