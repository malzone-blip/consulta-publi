# -*- coding: utf-8 -*-
"""Investigacao OSINT para due-diligence - com gate de finalidade e auditoria.

Reune busca de username (WhatsMyName + Sherlock), construtor de dorks e consulta
ao SpiderFoot. Antes de qualquer busca, o usuario declara a finalidade (uso
responsavel / LGPD) e cada consulta e registrada na auditoria.
"""
import pandas as pd
import streamlit as st

from core import audit, auth, ui
from core.modulos import POR_CHAVE
from services import osint

CHAVE = "investigacao"


def render():
    auth.exigir(CHAVE)
    modulo = POR_CHAVE[CHAVE]
    forcar, atualizar = ui.controle_atualizacao(CHAVE)
    topo = st.container()
    ui.cabecalho(modulo["titulo"], modulo["descricao"], None, atualizar, destino=topo)

    # ---- gate de finalidade (LGPD / uso responsavel) ----
    st.warning(
        "**Uso responsavel.** Estas ferramentas reunem informacoes publicas sobre "
        "pessoas e empresas. Use exclusivamente para due-diligence legitima da "
        "empresa (avaliar credenciado, fornecedor ou contraparte). Compilar dados "
        "de pessoa fisica para outros fins pode violar a LGPD. Cada consulta e "
        "registrada com seu usuario, data e alvo.", icon=":material/gavel:")
    aceite = st.checkbox(
        "Declaro que esta consulta tem finalidade de due-diligence corporativa.",
        key="osint_aceite")
    if not aceite:
        st.info("Marque a declaracao acima para habilitar as ferramentas.",
                icon=":material/lock:")
        return

    aba_user, aba_dork, aba_spider = st.tabs(
        ["Busca de username", "Construtor de buscas (dorks)", "SpiderFoot"])

    with aba_user:
        _aba_username(forcar)
    with aba_dork:
        _aba_dorks()
    with aba_spider:
        _aba_spiderfoot()


# ---------------------------------------------------------------------------
def _aba_username(forcar):
    st.caption(
        "Verifica em quais sites um mesmo nome de usuario existe. Fonte: dataset "
        "aberto WhatsMyName. Em rede corporativa restrita a varredura pode levar "
        "1-2 minutos, pois muitos sites externos respondem devagar."
    )
    c1, c2 = st.columns([0.55, 0.45])
    with c1:
        username = st.text_input("Nome de usuario (username)",
                                 placeholder="ex.: joaosilva (sem @, sem espacos)")
    with c2:
        escopo = st.radio("Escopo", ["Rapido (~35 sites principais)",
                                     "Completo (todos os sites)"],
                          key="wmn_escopo")

    usar_sherlock = False
    if osint.sherlock_disponivel():
        usar_sherlock = st.checkbox(
            "Tambem rodar o Sherlock (ferramenta externa, ~480 sites)",
            help="Mais abrangente que a busca rapida, porem LENTO nesta rede - "
                 "pode levar minutos e, se a rede estiver muito lenta, nao "
                 "terminar. Marque so quando puder esperar.")
    else:
        st.caption("Sherlock nao instalado. Para habilitar, um administrador roda "
                   "no venv: `python -m pip install sherlock-project`.")

    if st.button("Buscar", type="primary", icon=":material/person_search:") \
            and username.strip():
        # normaliza entradas comuns: remove @ e espacos nas pontas
        alvo = osint.normalizar_username(username)
        if not osint.username_valido(alvo):
            if " " in alvo:
                st.error(
                    "Nome de usuario nao tem espacos. Se voce quer buscar pelo "
                    "**nome de uma pessoa**, use a aba **Pe de Aranha** (tipo de "
                    "alvo 'Nome completo') - esta busca aqui e so para o "
                    "apelido/login de um site (ex.: joaosilva).",
                    icon=":material/error:")
            else:
                st.error(
                    "Nome de usuario invalido. Use de 2 a 40 caracteres: letras "
                    "(sem acento), numeros, ponto, hifen ou sublinhado. Nao use "
                    "acentos nem simbolos.", icon=":material/error:")
            return
        prioritarios = escopo.startswith("Rapido")
        audit.registrar(auth.usuario_atual()["usuario"], "OSINT_USERNAME",
                        "alvo=%s escopo=%s sherlock=%s"
                        % (alvo, "rapido" if prioritarios else "completo", usar_sherlock))

        with st.spinner("Verificando os sites... (pode levar ate 2 minutos)"):
            achados, checados, trunc, erro = osint.buscar_username(
                alvo, apenas_prioritarios=prioritarios)
        if erro:
            st.error(erro, icon=":material/error:")
            return

        st.success("Verificados %d sites; %d com conta encontrada."
                   % (checados, len(achados)), icon=":material/search:")
        if achados:
            ui.tabela(pd.DataFrame(achados), "wmn_%s" % alvo, altura=340,
                      config={"URL": st.column_config.LinkColumn("Perfil")})
        else:
            ui.vazio("Nenhuma conta encontrada nos sites verificados.")

        if usar_sherlock:
            with st.spinner("Rodando o Sherlock (pode demorar)..."):
                sher, err_s = osint.buscar_sherlock(alvo)
            st.markdown("##### Resultado do Sherlock")
            if err_s:
                st.error(err_s, icon=":material/error:")
            elif sher:
                ui.tabela(pd.DataFrame(sher), "sherlock_%s" % alvo, altura=300,
                          config={"URL": st.column_config.LinkColumn("Perfil")})
            else:
                ui.vazio("Sherlock nao encontrou contas.")

    ui.nota(
        "Encontrar um username num site nao confirma que e a mesma pessoa - nomes "
        "se repetem. Trate como indicio a confirmar, nunca como prova."
    )


def _aba_dorks():
    st.caption(
        "Monta buscas avancadas (dorks) do Google, Bing ou DuckDuckGo e entrega os "
        "links prontos. Nao faz requisicao nenhuma - apenas gera o link para voce "
        "abrir. Preencha o que tiver; templates sem dados sao omitidos."
    )
    c1, c2 = st.columns([0.3, 0.7])
    with c1:
        motor = st.selectbox("Buscador", list(osint.MOTORES.keys()))
    with c2:
        alvo = st.text_input("Nome / razao social", placeholder="Ex.: Empresa XYZ LTDA")
    c3, c4 = st.columns(2)
    with c3:
        dominio = st.text_input("Dominio (site)", placeholder="Ex.: xyz.com.br")
    with c4:
        cnpj = st.text_input("CNPJ / documento", placeholder="Ex.: 00.000.000/0001-00")

    gerar = st.button("Gerar buscas", type="primary", icon=":material/build:")
    if not (alvo.strip() or dominio.strip() or cnpj.strip()):
        st.info("Informe pelo menos um campo para gerar os links.",
                icon=":material/info:")
        return
    if not gerar:
        return

    # Auditoria so na acao deliberada (nao a cada rerun da tela).
    audit.registrar(auth.usuario_atual()["usuario"], "OSINT_DORK",
                    "alvo=%s dominio=%s" % (alvo.strip()[:40], dominio.strip()[:40]))
    dorks = osint.montar_dorks(motor, alvo.strip(), dominio.strip(), cnpj.strip())
    st.markdown("##### %d buscas geradas" % len(dorks))
    for rotulo, texto, url in dorks:
        col1, col2 = st.columns([0.62, 0.38])
        with col1:
            st.markdown("**%s**  \n`%s`" % (rotulo, texto))
        with col2:
            st.link_button("Abrir no %s" % motor, url, use_container_width=True,
                           icon=":material/open_in_new:")


def _aba_spiderfoot():
    st.caption(
        "O SpiderFoot e uma ferramenta de OSINT que roda como servico separado. "
        "Este painel fala com a instancia que a empresa mantiver. Configure a URL "
        "em Administracao > Fontes de Dados > Chaves de API."
    )
    if not osint.spiderfoot_configurado():
        st.info("Nenhuma instancia SpiderFoot configurada. Um administrador informa "
                "a URL (ex.: http://127.0.0.1:5001) na area de Fontes de Dados.",
                icon=":material/link_off:")
        with st.expander("Como subir o SpiderFoot", icon=":material/help:"):
            st.markdown(
                "1. `git clone https://github.com/smicallef/spiderfoot.git`\n"
                "2. criar venv e `pip install -r requirements.txt`\n"
                "3. subir so em loopback: `python sf.py -l 127.0.0.1:5001`\n"
                "4. informar `http://127.0.0.1:5001` na area de Fontes de Dados.")
        return

    ok, versao = osint.spiderfoot_ping()
    if not ok:
        st.error("A instancia SpiderFoot configurada nao respondeu (%s). Verifique "
                 "se o servico esta no ar." % versao, icon=":material/error:")
        return
    st.success("SpiderFoot conectado (versao %s)." % versao,
               icon=":material/check_circle:")

    st.caption(
        "O SpiderFoot investiga varios tipos de alvo - nao so nome de usuario. "
        "Escolha o tipo abaixo; o sistema formata o alvo do jeito que o SpiderFoot "
        "espera (nome de pessoa exige nome e sobrenome; telefone com DDI)."
    )
    c1, c2, c3 = st.columns([0.28, 0.42, 0.30])
    with c1:
        tipo_alvo = st.selectbox("Tipo de alvo", list(osint.TIPOS_ALVO_SF.keys()),
                                 format_func=lambda t: osint.TIPOS_ALVO_SF[t].split(" (")[0])
    with c2:
        alvo = st.text_input("Alvo",
                             placeholder=osint.TIPOS_ALVO_SF[tipo_alvo].split("(")[-1]
                             .rstrip(")") if "(" in osint.TIPOS_ALVO_SF[tipo_alvo]
                             else "Nome completo da pessoa")
    with c3:
        usecase = st.selectbox("Tipo de varredura",
                               ["passive", "investigate", "footprint"],
                               format_func=lambda u: {
                                   "passive": "Passiva (nao toca o alvo)",
                                   "investigate": "Investigativa",
                                   "footprint": "Footprint"}[u])

    if st.button("Iniciar varredura", type="primary", icon=":material/radar:") \
            and alvo.strip():
        alvo_fmt, err_fmt = osint.formatar_alvo_sf(tipo_alvo, alvo)
        if err_fmt:
            st.error(err_fmt, icon=":material/error:")
            return
        audit.registrar(auth.usuario_atual()["usuario"], "OSINT_SPIDERFOOT",
                        "tipo=%s alvo=%s usecase=%s"
                        % (tipo_alvo, alvo.strip()[:60], usecase))
        with st.spinner("Iniciando a varredura no SpiderFoot..."):
            scan_id, erro = osint.spiderfoot_iniciar_scan(
                "IntegraPublic %s" % alvo.strip()[:40], alvo_fmt, usecase)
        if erro:
            st.error(erro, icon=":material/error:")
        else:
            st.success("Varredura iniciada (id %s). Ela roda no SpiderFoot; volte "
                       "aqui em instantes e consulte os resultados pelo id." % scan_id,
                       icon=":material/check_circle:")
            st.session_state["sf_ultimo_scan"] = scan_id

    scan_id = st.text_input("Consultar resultados de um scan (id)",
                            value=st.session_state.get("sf_ultimo_scan", ""))
    if st.button("Buscar resultados", icon=":material/download:") and scan_id.strip():
        audit.registrar(auth.usuario_atual()["usuario"], "OSINT_SPIDERFOOT_RESULTADOS",
                        "scan=%s" % scan_id.strip()[:60])
        with st.spinner("Buscando resultados..."):
            dados, erro = osint.spiderfoot_resultados(scan_id.strip())
        if erro:
            st.error(erro, icon=":material/error:")
        elif not dados:
            ui.vazio("Sem resultados ainda (a varredura pode nao ter terminado).")
        else:
            ui.tabela(pd.DataFrame(dados), "spiderfoot_%s" % scan_id.strip(),
                      altura=380)

    ui.nota(
        "Prefira varredura passiva para due-diligence: ela usa apenas fontes "
        "publicas e nao envia trafego ao alvo, evitando alertar a contraparte."
    )
