# -*- coding: utf-8 -*-
"""Mercado de trabalho: indicadores para Recursos Humanos."""
import streamlit as st

from core import auth, ui
from core.modulos import POR_CHAVE
from services import bcb, externas

CHAVE = "rh"

# Agregados do IBGE relevantes para RH (verificados na varredura).
INDICADORES_IBGE = {
    "Taxa de desocupacao (PNAD)": {"agregado": 6381, "variavel": 4099},
    "Rendimento medio real (PNAD)": {"agregado": 6390, "variavel": 5933},
}


def render():
    auth.exigir(CHAVE)
    modulo = POR_CHAVE[CHAVE]
    forcar, atualizar = ui.controle_atualizacao(CHAVE)
    topo = st.container()

    ui.cabecalho(modulo["titulo"], modulo["descricao"], None, atualizar, destino=topo)

    # ---- salario minimo (SGS 1619) ----
    with st.spinner("Carregando indicadores..."):
        sm, r_sm = bcb.serie_sgs(1619, 3650, forcar)

    if ui.verificar(r_sm, "salario minimo") and not sm.empty:
        atual = float(sm.iloc[-1]["valor"])
        doze = sm[sm["data"] <= (sm.iloc[-1]["data"] - __import__("pandas").Timedelta(days=350))]
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Salario minimo vigente", ui.moeda(atual),
                      help="Referencia: %s" % sm.iloc[-1]["data"].strftime("%m/%Y"))
        with c2:
            if not doze.empty:
                anterior = float(doze.iloc[-1]["valor"])
                var = ((atual / anterior) - 1) * 100 if anterior else 0
                st.metric("Reajuste em 12 meses", "%s%%" % ui.num(var, 2))
        with c3:
            st.metric("Piso mensal x 13,33 (custo anual base)",
                      ui.moeda(atual * 13.33),
                      help="Estimativa simples incluindo 13o; nao substitui calculo "
                           "de encargos.")
        st.caption(r_sm.selo())

    st.write("")
    aba_ind, aba_hist = st.tabs(["Indicadores de emprego", "Historico do salario minimo"])

    with aba_ind:
        nome = st.selectbox("Indicador", list(INDICADORES_IBGE.keys()))
        cfg = INDICADORES_IBGE[nome]
        with st.spinner("Consultando o IBGE..."):
            df, resp = externas.ibge_agregado(cfg["agregado"], cfg["variavel"],
                                              "-16", "N1[all]", forcar)
        if ui.verificar(resp, "indicadores do IBGE"):
            if df.empty:
                ui.vazio("Sem dados retornados para este indicador.")
            else:
                serie = df.copy()
                serie["Periodo"] = serie["Periodo"].astype(str)
                ult = serie.iloc[-1]
                st.metric("Ultimo valor - %s" % ult["Periodo"],
                          "%s %s" % (ui.num(ult["Valor"], 1), ult.get("Unidade", "")))
                st.line_chart(serie.set_index("Periodo")["Valor"], height=300,
                              color="#2563EB")
                ui.tabela(serie.sort_values("Periodo", ascending=False),
                          "rh_%s" % cfg["agregado"], altura=300)
                st.caption(resp.selo())

    with aba_hist:
        if not sm.empty:
            ui.grafico_linhas(sm.set_index("data")[["valor"]].rename(
                columns={"valor": "Salario minimo (R$)"}), altura=320, titulo_y="R$")
            exibir = sm.copy()
            exibir["data"] = exibir["data"].dt.strftime("%d/%m/%Y")
            ui.tabela(exibir.rename(columns={"data": "Vigencia", "valor": "Valor (R$)"})
                      .sort_values("Vigencia", ascending=False),
                      "salario_minimo", altura=300)

    ui.nota(
        "Fontes: salario minimo pelo SGS/Banco Central (serie 1619); desocupacao e "
        "rendimento pela PNAD Continua do IBGE. Indicadores de apoio ao "
        "planejamento de pessoal - nao substituem a folha nem a convencao coletiva."
    )
