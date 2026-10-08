# -*- coding: utf-8 -*-
"""Open Finance: diretorio de participantes e catalogo de APIs abertas."""
import streamlit as st

from core import auth, ui
from core.modulos import POR_CHAVE
from services import bcb, externas

CHAVE = "openfinance"


def render():
    auth.exigir(CHAVE)
    modulo = POR_CHAVE[CHAVE]
    forcar, atualizar = ui.controle_atualizacao(CHAVE)
    topo = st.container()  # cabecalho fica no topo, preenchido apos a consulta

    with st.spinner("Consultando o diretorio do Open Finance..."):
        df, resp = externas.openfinance_participantes(forcar)

    ui.cabecalho(modulo["titulo"], modulo["descricao"], resp, atualizar, destino=topo)
    if not ui.verificar(resp, "diretorio do Open Finance"):
        return

    aba_part, aba_end, aba_dasfn = st.tabs(
        ["Participantes", "Endpoints publicados", "Catalogo DASFN (BCB)"])

    with aba_part:
        if df.empty:
            ui.vazio("O diretorio nao retornou participantes.")
        else:
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Instituicoes participantes", ui.inteiro(len(df)))
            with c2:
                st.metric("Marcas cadastradas", ui.inteiro(df["Qtd. marcas"].sum()))
            with c3:
                ativas = int((df["Situacao"] == "Active").sum())
                st.metric("Com situacao ativa", ui.inteiro(ativas))

            busca = st.text_input("Buscar instituicao ou CNPJ",
                                  placeholder="Ex.: NUBANK, 00000000000191",
                                  key="of_busca_part")
            filtrado = df
            if busca:
                alvo = busca.strip().upper()
                filtrado = df[
                    df["Instituicao"].astype(str).str.upper().str.contains(alvo, na=False)
                    | df["CNPJ"].astype(str).str.contains(
                        "".join(ch for ch in alvo if ch.isdigit()) or "@@", na=False)
                ]
            ui.tabela(filtrado, "openfinance_participantes", altura=430)

    with aba_end:
        with st.spinner("Extraindo endpoints..."):
            df_end, r_end = externas.openfinance_endpoints(forcar)
        if ui.verificar(r_end, "endpoints do Open Finance"):
            if df_end.empty:
                ui.vazio("Nenhum endpoint publicado no diretorio.")
            else:
                familias = sorted(df_end["Familia"].dropna().unique().tolist())
                abertas = [f for f in familias if f in externas.FAMILIAS_ABERTAS]
                escolha = st.multiselect(
                    "Familias de API", familias, default=abertas or familias[:3],
                    help="As familias de dados abertos nao exigem certificado nem "
                         "consentimento - basta um GET.",
                )
                filtrado = df_end[df_end["Familia"].isin(escolha)] if escolha else df_end
                st.metric("Endpoints listados", ui.inteiro(len(filtrado)))
                ui.tabela(filtrado, "openfinance_endpoints", altura=420)

                st.markdown("##### O que da para consumir sem credencial")
                for familia, texto in externas.FAMILIAS_ABERTAS.items():
                    st.markdown("- **`%s`** - %s" % (familia, texto))
                ui.nota(
                    "Estas tres familias formam a fase de dados abertos do Open "
                    "Finance: qualquer sistema pode ler taxas, tarifas, condicoes de "
                    "produto e canais de atendimento de cada instituicao. Dados de "
                    "cliente e iniciacao de pagamento exigem ser instituicao regulada, "
                    "com certificado ICP/OFB e OAuth 2.0 - isso esta fora do escopo "
                    "deste sistema."
                )

    with aba_dasfn:
        st.caption(
            "O DASFN e o catalogo do proprio Banco Central com os endpoints de dados "
            "abertos declarados pelas instituicoes do SFN, incluindo Pix Saque e "
            "Pix Troco."
        )
        api = st.selectbox("API", ["(todas)", "canais_atendimento", "produtos_servicos",
                                   "pix_saque", "pix_troco"], key="dasfn_api")
        with st.spinner("Carregando catalogo..."):
            df_d, r_d = bcb.dasfn_recursos("" if api == "(todas)" else api, forcar)
        if ui.verificar(r_d, "catalogo DASFN"):
            if df_d.empty:
                ui.vazio("Nenhum recurso para esse filtro.")
            else:
                st.metric("Recursos publicados", ui.inteiro(len(df_d)))
                exibir = df_d.rename(columns={
                    "Api": "API", "Versao": "Versao",
                    "NomeInstituicao": "Instituicao", "CnpjInstituicao": "CNPJ",
                    "Recurso": "Recurso", "Situacao": "Situacao",
                    "URLDados": "URL de dados", "URLConsulta": "URL de consulta"})
                colunas = [c for c in ("Instituicao", "API", "Versao", "Recurso",
                                       "Situacao", "URL de dados")
                           if c in exibir.columns]
                ui.tabela(exibir[colunas] if colunas else exibir, "dasfn_recursos",
                          altura=420, config={
                              "URL de dados": st.column_config.LinkColumn("URL de dados")})
