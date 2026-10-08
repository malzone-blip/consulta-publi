# -*- coding: utf-8 -*-
"""Estado das fontes publicas e do cache de atualizacao automatica."""
import pandas as pd
import streamlit as st

from core import audit, auth, db, http, ui
from core.config import (CFG_CHAVE_CGU, CFG_CHAVE_DATAJUD, TTL_CADASTRAL, TTL_DIARIO,
                         TTL_INTRADIARIO, TTL_MENSAL)
from core.modulos import MODULOS, POR_CHAVE
from services import osint
from services import transparencia as tp

CHAVE = "admin_fontes"

# Endpoint leve de cada fonte, usado apenas para teste de disponibilidade.
SONDAS = {
    "BCB / SGS - series temporais":
        "https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados/ultimos/1?formato=json",
    "BCB / PTAX - cambio":
        "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/Moedas?$top=1&$format=json",
    "BCB / Expectativas - Focus":
        "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/"
        "ExpectativasMercadoAnuais?$top=1&$format=json",
    "BCB / Instituicoes em funcionamento":
        "https://olinda.bcb.gov.br/olinda/servico/Instituicoes_em_funcionamento/versao/v1/"
        "odata/DominiosVerificados?$top=1&$format=json",
    "BCB / Agencias":
        "https://olinda.bcb.gov.br/olinda/servico/Informes_Agencias/versao/v1/odata/"
        "Agencias?$top=1&$format=json",
    "BCB / Correspondentes":
        "https://olinda.bcb.gov.br/olinda/servico/Informes_Correspondentes/versao/v1/"
        "odata/Correspondentes?$top=1&$format=json",
    "BCB / Penalidades (inabilitados)":
        "https://olinda.bcb.gov.br/olinda/servico/Gepad_QuadrosGeraisInternet/versao/v1/"
        "odata/QuadroGeralInabilitados?$top=1&$format=json",
    "BCB / IF.data":
        "https://olinda.bcb.gov.br/olinda/servico/IFDATA/versao/v1/odata/"
        "ListaDeRelatorio()?$top=1&$format=json",
    "BCB / Pix - DICT":
        "https://olinda.bcb.gov.br/olinda/servico/Pix_DadosAbertos/versao/v1/odata/"
        "PixUsuariosCadastradosDICT?$top=1&$format=json",
    "BCB / SPI":
        "https://olinda.bcb.gov.br/olinda/servico/SPI/versao/v1/odata/"
        "PixLiquidadosAtual?$top=1&$format=json",
    "BCB / STR":
        "https://olinda.bcb.gov.br/olinda/servico/STR/versao/v2/odata/"
        "STRLiquidadosAtual?$top=1&$format=json",
    "BCB / Tarifas bancarias":
        "https://olinda.bcb.gov.br/olinda/servico/Informes_ListaValoresDeServicoBancario/"
        "versao/v1/odata/GruposConsolidados?$top=1&$format=json",
    "BCB / Ranking de ouvidorias":
        "https://olinda.bcb.gov.br/olinda/servico/RankingOuvidorias/versao/v1/odata/"
        "Periodos?$top=1&$format=json",
    "BCB / DASFN - catalogo do SFN":
        "https://olinda.bcb.gov.br/olinda/servico/DASFN/versao/v1/odata/"
        "Recursos?$top=1&$format=json",
    "IBGE / Localidades":
        "https://servicodados.ibge.gov.br/api/v1/localidades/estados/33",
    "BrasilAPI / Bancos": "https://brasilapi.com.br/api/banks/v1",
    "Open Finance / Diretorio":
        "https://data.directory.openbankingbrasil.org.br/participants",
    "Siscomex / NCM-TEC":
        "https://portalunico.siscomex.gov.br/classif/api/publico/nomenclatura/"
        "download/json",
    "ComexStat / Atualizacao":
        "https://api-comexstat.mdic.gov.br/general/dates/updated",
    "SICONFI / Entes": "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/entes",
    "PNCP / Contratos":
        "https://pncp.gov.br/api/consulta/v1/contratos?dataInicial=20260101&"
        "dataFinal=20260105&pagina=1",
    "Compras.gov.br / Catalogo":
        "https://dadosabertos.compras.gov.br/modulo-material/1_consultarGrupoMaterial"
        "?pagina=1&tamanhoPagina=10",
    "Camara / Dados Abertos":
        "https://dadosabertos.camara.leg.br/api/v2/referencias/proposicoes/siglaTipo",
    "Senado / Dados Abertos":
        "https://legis.senado.leg.br/dadosabertos/senador/lista/atual",
    "Querido Diario / OKBR":
        "https://queridodiario.ok.org.br/api/cities?city_name=Campinas",
    "CVM / Companhias abertas":
        "https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv",
    "IBGE / CNAE": "https://servicodados.ibge.gov.br/api/v2/cnae/secoes",
    "CGU / Portal da Transparencia (catalogo)":
        "https://api.portaldatransparencia.gov.br/v3/api-docs",
    "Nominatim / OpenStreetMap":
        "https://nominatim.openstreetmap.org/search?q=Brasilia&format=json&limit=1",
}

POLITICA = [
    ("Cotacoes e dados intradiarios", TTL_INTRADIARIO),
    ("Series diarias e Focus", TTL_DIARIO),
    ("Estatisticas mensais (Pix, meios de pagamento)", TTL_MENSAL),
    ("Cadastros (instituicoes, agencias, tarifas)", TTL_CADASTRAL),
]


def render():
    auth.exigir(CHAVE)
    modulo = POR_CHAVE[CHAVE]
    eu = auth.usuario_atual()
    ui.cabecalho(modulo["titulo"], modulo["descricao"])

    aba_cache, aba_teste, aba_catalogo, aba_chaves = st.tabs(
        ["Cache e atualizacao", "Testar disponibilidade", "Catalogo de APIs",
         "Chaves de API"])

    with aba_cache:
        _aba_cache(eu)
    with aba_teste:
        _aba_teste()
    with aba_catalogo:
        _aba_catalogo()
    with aba_chaves:
        _aba_chaves(eu)


def _aba_cache(eu):
    st.markdown("##### Como o sistema se mantem atualizado")
    st.caption(
        "A atualizacao e sob demanda, por vencimento: nao existe processo rodando "
        "em segundo plano. Ao abrir uma tela, o sistema compara a idade da copia "
        "local com o prazo abaixo - dentro do prazo entrega a copia, vencido busca "
        "na fonte. Sem ninguem abrir a tela, nada e buscado. Se a fonte estiver "
        "fora do ar, a ultima copia boa continua sendo exibida, marcada como "
        "defasada: o sistema nunca fica em branco."
    )
    politica = pd.DataFrame([
        {"Natureza do dado": nome,
         "Validade da copia": "%d minutos" % (ttl // 60) if ttl < 3600
                              else "%d horas" % (ttl // 3600)}
        for nome, ttl in POLITICA
    ])
    st.dataframe(politica, use_container_width=True, hide_index=True)

    st.write("")
    st.markdown("##### Conteudo atual do cache")
    itens = http.estado_cache()
    if not itens:
        ui.vazio("O cache esta vazio. Ele se preenche conforme as telas sao abertas.")
    else:
        df = pd.DataFrame(itens).drop(columns=["arquivo"], errors="ignore")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Fontes em cache", ui.inteiro(len(df)))
        with c2:
            st.metric("Espaco ocupado", "%s KB" % ui.num(df["Tamanho (KB)"].sum(), 1))
        with c3:
            st.metric("Copia mais antiga", "%s min" % ui.num(df["Idade (min)"].max(), 0))
        ui.tabela(df.sort_values("Idade (min)", ascending=False), "cache_fontes",
                  altura=360)

    st.write("")
    c1, c2 = st.columns([0.28, 0.72])
    with c1:
        if st.button("Limpar todo o cache", use_container_width=True,
                     icon=":material/delete_sweep:"):
            n = http.limpar_cache()
            st.cache_data.clear()
            audit.registrar(eu["usuario"], "CACHE_LIMPO", "%d arquivo(s)" % n)
            st.success("%d arquivo(s) removido(s). As proximas consultas buscarao "
                       "tudo novamente nas fontes." % n, icon=":material/check_circle:")
    with c2:
        st.caption(
            "Use apenas se suspeitar de dado incorreto: a primeira consulta apos a "
            "limpeza fica mais lenta, pois tudo e rebuscado nas fontes."
        )


def _aba_teste():
    st.caption(
        "Faz uma chamada minima em cada fonte e mede o tempo de resposta. Nao usa "
        "cache: e o estado real das APIs agora."
    )
    if st.button("Testar todas as fontes", type="primary",
                 icon=":material/network_check:"):
        linhas = []
        barra = st.progress(0.0, "Testando...")
        total = len(SONDAS)
        for i, (nome, url) in enumerate(SONDAS.items(), start=1):
            ok, detalhe, ms = http.testar(url)
            linhas.append({
                "Fonte": nome,
                "Situacao": "Disponivel" if ok else "Indisponivel",
                "Resposta": detalhe,
                "Tempo (ms)": ms,
            })
            barra.progress(i / total, "Testando %s..." % nome)
        barra.empty()

        df = pd.DataFrame(linhas)
        indisponiveis = int((df["Situacao"] == "Indisponivel").sum())
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Fontes testadas", ui.inteiro(len(df)))
        with c2:
            st.metric("Indisponiveis", ui.inteiro(indisponiveis))
        with c3:
            st.metric("Tempo medio", "%s ms" % ui.num(df["Tempo (ms)"].mean(), 0))
        if indisponiveis:
            st.warning(
                "%d fonte(s) nao responderam. Os modulos correspondentes continuam "
                "funcionando com a ultima copia local." % indisponiveis,
                icon=":material/warning:",
            )
        else:
            st.success("Todas as fontes responderam.", icon=":material/check_circle:")
        ui.tabela(df, "teste_fontes", altura=520)


def _aba_chaves(eu):
    st.caption(
        "A maioria das fontes e totalmente aberta e nao aparece aqui. Estas duas "
        "usam chave: o Portal da Transparencia exige uma chave gratuita sua; o "
        "DataJud ja vem com a chave publica do CNJ e so precisa ser trocada se o "
        "orgao rotaciona-la."
    )

    # --- CGU / Portal da Transparencia ---
    st.markdown("##### Portal da Transparencia (CGU)")
    tem = tp.tem_chave()
    if tem:
        st.success("Chave cadastrada. O modulo Portal da Transparencia esta ativo "
                   "no menu.", icon=":material/check_circle:")
    else:
        st.warning("Sem chave. O modulo Portal da Transparencia fica visivel apenas "
                   "para administradores ate a chave ser cadastrada.",
                   icon=":material/key_off:")
    st.link_button("Solicitar chave gratuita (gov.br)", tp.URL_CADASTRO,
                   icon=":material/open_in_new:")
    with st.form("form_chave_cgu"):
        valor = st.text_input("Chave da API (cabecalho chave-api-dados)",
                              type="password",
                              placeholder="cole aqui o token recebido por e-mail")
        c1, c2 = st.columns([0.3, 0.7])
        with c1:
            salvar = st.form_submit_button("Validar e salvar", type="primary",
                                           use_container_width=True)
        with c2:
            remover = st.form_submit_button("Remover chave",
                                            use_container_width=True)
    if salvar:
        ok, msg = tp.testar_chave(valor)
        if ok:
            db.definir_config(CFG_CHAVE_CGU, valor, eu["usuario"])
            audit.registrar(eu["usuario"], "CHAVE_CGU_DEFINIDA",
                            "Chave do Portal da Transparencia validada e salva.")
            st.cache_data.clear()
            st.success(msg + " O modulo ja aparece no menu.",
                       icon=":material/check_circle:")
            st.rerun()
        else:
            st.error(msg, icon=":material/error:")
    if remover:
        db.remover_config(CFG_CHAVE_CGU)
        audit.registrar(eu["usuario"], "CHAVE_CGU_REMOVIDA", "Chave removida.")
        st.cache_data.clear()
        st.info("Chave removida.")
        st.rerun()

    st.divider()

    # --- DataJud / CNJ ---
    st.markdown("##### DataJud (CNJ)")
    atual = db.obter_config(CFG_CHAVE_DATAJUD, "")
    st.caption(
        "O DataJud ja funciona com a chave publica que o proprio CNJ divulga - nao "
        "e necessario fazer nada. Preencha abaixo apenas se o CNJ publicar uma nova "
        "chave e as consultas comecarem a falhar."
        + (" Ha uma chave personalizada salva." if atual else
           " Usando a chave publica padrao."))
    with st.form("form_chave_datajud"):
        valor_dj = st.text_input("Chave personalizada do DataJud (opcional)",
                                 type="password")
        c1, c2 = st.columns([0.3, 0.7])
        with c1:
            salvar_dj = st.form_submit_button("Salvar", use_container_width=True)
        with c2:
            limpar_dj = st.form_submit_button("Voltar a chave padrao",
                                              use_container_width=True)
    if salvar_dj and valor_dj.strip():
        db.definir_config(CFG_CHAVE_DATAJUD, valor_dj, eu["usuario"])
        audit.registrar(eu["usuario"], "CHAVE_DATAJUD_DEFINIDA", "Chave personalizada.")
        st.cache_data.clear()
        st.success("Chave do DataJud atualizada.")
        st.rerun()
    if limpar_dj:
        db.remover_config(CFG_CHAVE_DATAJUD)
        audit.registrar(eu["usuario"], "CHAVE_DATAJUD_REMOVIDA", "Voltou ao padrao.")
        st.cache_data.clear()
        st.info("Voltou a usar a chave publica padrao do CNJ.")
        st.rerun()

    st.divider()

    # --- SpiderFoot (OSINT) ---
    st.markdown("##### SpiderFoot (modulo de Investigacao)")
    atual_sf = db.obter_config(osint.CFG_SPIDERFOOT_URL, "")
    st.caption(
        "O SpiderFoot roda como servico separado. Informe aqui a URL da instancia "
        "para o modulo de Investigacao poder consulta-la (ex.: http://127.0.0.1:5001). "
        "Deixe em branco para desabilitar essa aba."
        + (" Instancia configurada: %s" % atual_sf if atual_sf else ""))
    with st.form("form_spiderfoot"):
        url_sf = st.text_input("URL da instancia SpiderFoot", value=atual_sf,
                               placeholder="http://127.0.0.1:5001")
        c1, c2 = st.columns([0.3, 0.7])
        with c1:
            salvar_sf = st.form_submit_button("Salvar e testar", use_container_width=True)
        with c2:
            limpar_sf = st.form_submit_button("Remover", use_container_width=True)
    if salvar_sf:
        db.definir_config(osint.CFG_SPIDERFOOT_URL, url_sf, eu["usuario"])
        st.cache_data.clear()
        ok, versao = osint.spiderfoot_ping()
        audit.registrar(eu["usuario"], "SPIDERFOOT_CONFIG", "url=%s ok=%s" % (url_sf, ok))
        if ok:
            st.success("Conectado ao SpiderFoot (versao %s)." % versao,
                       icon=":material/check_circle:")
        else:
            st.warning("URL salva, mas a instancia nao respondeu agora (%s). "
                       "Verifique se o servico esta no ar." % versao,
                       icon=":material/warning:")
        st.rerun()
    if limpar_sf:
        db.remover_config(osint.CFG_SPIDERFOOT_URL)
        st.cache_data.clear()
        audit.registrar(eu["usuario"], "SPIDERFOOT_CONFIG", "removido")
        st.info("Instancia SpiderFoot removida.")
        st.rerun()


def _aba_catalogo():
    st.caption(
        "Todas as APIs publicas consumidas pelo sistema, e em que modulo cada uma "
        "aparece. Nenhuma exige chave de acesso ou contrato."
    )
    linhas = []
    for m in MODULOS:
        for fonte in m.get("fontes", []):
            linhas.append({"Fonte": fonte, "Modulo": m["titulo"], "Grupo": m["grupo"]})
    df = pd.DataFrame(linhas)
    if df.empty:
        ui.vazio()
        return
    resumo = (df.groupby("Fonte")
              .agg(**{"Modulos que usam": ("Modulo", lambda s: ", ".join(sorted(set(s)))),
                      "Quantidade": ("Modulo", "nunique")})
              .reset_index().sort_values("Fonte"))
    st.metric("APIs publicas integradas", ui.inteiro(len(resumo)))
    ui.tabela(resumo, "catalogo_apis", altura=460)
