# IntegraPublic

**Sistema Geral Interdepartamental — dados públicos oficiais**

Sistema web multiusuário em Python + Streamlit que reúne, em uma única interface,
as principais APIs públicas e abertas do Banco Central do Brasil, do IBGE, do
Open Finance e da BrasilAPI. Nenhuma das fontes exige chave de acesso, contrato
ou credencial.

- **Acesso na rede:** http://10.10.1.225:6789
- **Instalação:** ambiente virtual próprio (`.venv`), isolado dos demais sistemas da máquina
- **Banco de dados:** SQLite local (`dados/integrapublic.db`), modo WAL

---

## 1. Instalação

Abra o PowerShell na pasta do projeto e execute:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\instalar.ps1
```

O script cria o `.venv`, atualiza o pip e instala as dependências. Como esta
máquina hospeda vários sistemas, **tudo fica contido na pasta do projeto** — nada
é instalado no Python global.

### Liberar a porta no firewall (uma única vez, como administrador)

```powershell
New-NetFirewallRule -DisplayName "IntegraPublic 6789" -Direction Inbound -Protocol TCP -LocalPort 6789 -Action Allow
```

## 2. Iniciar o sistema

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\iniciar.ps1
```

Ou dê dois cliques em `scripts\iniciar.bat`.

O servidor escuta em `0.0.0.0:6789`, ficando acessível em **http://10.10.1.225:6789**
para qualquer máquina da rede.

### Deixar rodando permanentemente

O Streamlit para quando a janela do console fecha. Para manter o serviço no ar:

- **Agendador de Tarefas do Windows** — crie uma tarefa "Ao iniciar o computador",
  com "Executar estando o usuário conectado ou não", apontando para
  `.venv\Scripts\python.exe` com os argumentos
  `-m streamlit run app.py --server.address 0.0.0.0 --server.port 6789`
  e "Iniciar em" na pasta do projeto; ou
- **NSSM** (`nssm install IntegraPublic`), que registra como serviço do Windows.

## 3. Primeiro acesso

| Usuário | Senha       |
|---------|-------------|
| `admin` | `mudar@123` |

O sistema **exige a troca da senha imediatamente** no primeiro login. Só depois
disso o menu é liberado.

## 4. Usuários e permissões

Em **Administração › Usuários e Permissões** o administrador pode:

- criar usuários — sempre com a senha padrão `mudar@123` e troca obrigatória no
  primeiro acesso;
- editar nome, e-mail, setor, perfil e situação (ativo/inativo);
- conceder ou revogar acesso **módulo a módulo**;
- redefinir a senha de volta para a padrão;
- excluir usuários.

O menu lateral é montado a partir dessas permissões: cada pessoa vê apenas o que
lhe foi liberado. Revogar um acesso tem efeito na próxima interação do usuário —
não é preciso esperá-lo sair do sistema.

**Travas de segurança:** não é possível excluir o próprio usuário, nem excluir,
desativar ou rebaixar o último administrador ativo. Cinco senhas erradas seguidas
bloqueiam o login por 10 minutos. Senhas são gravadas com PBKDF2-HMAC-SHA256,
260.000 iterações e salt individual — nunca em texto puro.

Toda ação relevante fica registrada em **Administração › Auditoria**.

> **A sessão vive na aba do navegador.** Atualizar a página (F5) ou abrir o
> sistema em outra aba exige login de novo. É o comportamento padrão do
> Streamlit e o mais seguro: nada de credencial fica guardado no navegador. Se
> preferir um "manter conectado", isso é um ajuste à parte — hoje não existe.

## 5. Atualização automática dos dados

A atualização é **sob demanda, por vencimento** — e não um processo rodando em
segundo plano. Não há nenhum serviço, thread ou timer atualizando dados sozinho.

Cada cópia local carrega um prazo de validade. Quando alguém abre uma tela, o
sistema compara a idade da cópia com esse prazo: dentro do prazo, entrega a
cópia; vencido, busca na fonte e regrava. **Sem ninguém abrindo a tela, nada é
buscado.**

| Natureza do dado                              | Validade da cópia |
|-----------------------------------------------|-------------------|
| Cotações e dados intradiários                 | 15 minutos        |
| Séries diárias e Relatório Focus              | 6 horas           |
| Estatísticas mensais (Pix, meios de pagamento)| 12 horas          |
| Cadastros (instituições, agências, tarifas)   | 24 horas          |

O que isso garante: o dado exibido nunca está mais velho que o prazo, porque a
conferência ocorre no momento de montar a tela. O que isso **não** faz: adiantar
trabalho. Quem abrir a tela logo após o vencimento espera a carga.

Se a fonte estiver fora do ar, o sistema **continua exibindo a última cópia boa**,
marcada com um aviso de defasagem, e volta a tentar sozinho na consulta seguinte.
Cada tela mostra um selo com a procedência e o horário do dado, e tem o botão
**Atualizar agora** para forçar a busca.

Opcionalmente, agende `scripts\atualizar_cache.py` no Agendador de Tarefas
(ex.: 06h30 diariamente) para que tudo já esteja carregado antes do expediente.

O estado de todas as fontes, com teste de disponibilidade ao vivo, fica em
**Administração › Fontes de Dados**.

## 6. APIs públicas integradas

### Banco Central — SGS
Séries temporais: Selic (meta, diária, acumulada), CDI, IPCA (mensal e 12 meses),
IGP-M, INPC, TR, dólar, euro, poupança, reservas internacionais, saldo de crédito,
inadimplência, endividamento das famílias, IBC-Br.

### Banco Central — Olinda (OData)
| Serviço | Uso no sistema |
|---|---|
| `PTAX` | cotações de todas as moedas, compra/venda/paridade |
| `Expectativas` | Relatório Focus: anuais, mensais, trimestrais, Selic, Top 5 |
| `Instituicoes_em_funcionamento` | bancos, cooperativas, consórcios, demais sociedades e **domínios verificados** |
| `Informes_Agencias` | agências por UF, instituição e município |
| `Informes_PostosDeAtendimento` | PAs, PAEs e postos avançados |
| `Informes_Correspondentes` | rede de correspondentes bancários e serviços autorizados |
| `Gepad_QuadrosGeraisInternet` | inabilitados e proibidos pelo BCB |
| `IFDATA` | balanços e indicadores prudenciais por trimestre |
| `Pix_DadosAbertos` | chaves no DICT, transações por perfil, **estatísticas de fraude e MED** |
| `SPI` | Pix liquidado e disponibilidade do sistema |
| `STR` | liquidação de reservas |
| `MPV_DadosAbertos` | Pix × TED × boleto × cheque × DOC |
| `Informes_ListaValoresDeServicoBancario` | tarifas: mínimo, máximo e médio do mercado |
| `Informes_ListaTarifasPorInstituicaoFinanceira` | tarifas por instituição |
| `RankingOuvidorias` | qualidade das ouvidorias |
| `DASFN` | catálogo das APIs abertas do SFN, incluindo Pix Saque e Pix Troco |

### Fora do Banco Central
- **Open Finance Brasil** — diretório público de participantes e os endpoints das
  famílias abertas (`products-services`, `channels`, `discovery`), que dispensam
  certificado e consentimento.
- **IBGE** — estados, municípios, códigos IBGE e séries do SIDRA (IPCA, INPC, PNAD).
- **BrasilAPI** — CNPJ, CEP, bancos (COMPE/ISPB), participantes do Pix, feriados.

### Fontes por área de origem
| Área | Fonte | O que traz |
|---|---|---|
| Comércio exterior | Siscomex, ComexStat (MDIC) | NCM/TEC e exportação/importação por país, NCM, UF, bloco |
| Setor público / Controladoria | IBGE, CVM, SICONFI, PNCP, Compras.gov | CNAE, companhias abertas e **fundos de investimento** (cadastro + informe diário de cota/PL); RREO/RGF de estados e municípios; contratos, atas e editais; catálogo de materiais |
| Jurídico | DataJud (CNJ), Câmara, Senado, Querido Diário | processos de **todos os tribunais**, tramitação legislativa, diários oficiais municipais |
| RH | BCB/SGS, IBGE/PNAD | salário mínimo, desocupação, rendimento |
| Administrativo/Facilities | BCB/SGS, Nominatim | IGP-M/INCC, simulador de reajuste, geocodificação |
| Compliance | CGU, WhatsMyName, Sherlock, SpiderFoot | console dos **106 endpoints** da Transparência + **Verificar Credenciado** (CNPJ contra CEIS/CNEP/CEPIM/leniência de uma vez) + due-diligence OSINT |

> Qual setor consome cada módulo está declarado explicitamente no catálogo
> (`core/modulos.py`, campo `departamentos`) — veja a seção 7.

### Chaves de API (Administração › Fontes de Dados › Chaves de API)
- **Portal da Transparência (CGU)** — chave gratuita (cadastro gov.br). Sem ela, os
  módulos *Portal da Transparência* e *Verificar Credenciado* ficam ocultos no menu
  (visíveis só para administradores, para configurar).
- **DataJud (CNJ)** — já vem com a chave pública do CNJ; nada a fazer.
- **SpiderFoot** — URL de uma instância que a empresa rode à parte (opcional).

### Módulo de Investigação (OSINT) — como funciona e limites
Fica atrás de permissão dedicada e **exige declaração de finalidade** (due-diligence)
a cada uso; toda consulta é auditada. Guardrails de segurança: username validado por
whitelist, Sherlock via subprocess sem shell, sessão HTTP isolada, e **bloqueio anti-SSRF**
que recusa qualquer host que resolva para a rede interna (protege a própria
`10.10.1.225` e endereços de metadados).

> **Velocidade da busca de username.** Depende da rede de saída do servidor. Nesta
> VM, que parece ter proxy/firewall corporativo, uma varredura completa (700 sites)
> leva minutos e muitos sites expiram. Por isso o padrão é o *quick scan* (~37 sites
> principais). Numa rede sem restrição é questão de segundos.

- **Sherlock** é opcional. Para habilitar: `.venv\Scripts\python.exe -m pip install sherlock-project`.
- **SET (Social-Engineer Toolkit) não foi integrado** — é um framework ofensivo de
  phishing, não uma fonte de dados; não cabe num painel de consulta.

#### SpiderFoot (instalado em `C:\Sistemas Pronto\spiderfoot`)
Roda como serviço separado, só em loopback (`127.0.0.1:5001`), e o IntegraPublic
fala com ele por HTTP. A URL já está cadastrada na configuração.
- **Subir o serviço:** dois cliques em `C:\Sistemas Pronto\spiderfoot\IniciarSpiderFoot.bat`.
  Ele detecta se já está no ar. Como o IntegraPublic, **cai quando a janela fecha** —
  para uso contínuo, deixe a janela aberta ou registre no Agendador de Tarefas.
- Prefira varredura **passiva** (padrão): usa só fontes públicas, não toca o alvo.
- Um scan por vez: uma varredura completa consome CPU e, em paralelo, satura o serviço.

### Datas em todas as telas
As datas exibidas seguem o padrão brasileiro **dd/mm/aaaa**. O selo "Atualizado…"
usa esse formato, e **toda tabela** normaliza automaticamente qualquer data que a
fonte devolva em formato ISO (aaaa-mm-dd ou com hora) para dd/mm/aaaa — feito de
forma central em `core/ui.py` (`_converter_datas`), sem depender de ajuste tela a
tela. Meses de referência (ex.: "09/2026") permanecem como mês/ano de propósito.

### Detalhes técnicos que costumam quebrar integrações
Ficam resolvidos no código, mas vale saber:

- No Olinda, **funções parametrizadas exigem os argumentos entre parênteses**;
  chamá-las sem isso devolve `HTTP 400 - The URI is malformed`.
- A **PTAX usa datas em `MM-DD-AAAA`** entre aspas simples, não `dd/MM`.
- As **estatísticas de fraude do Pix são anuais** (`Database='2025'`), enquanto as
  de transações são mensais (`Database='202606'`) e as de chaves usam o último dia
  do mês (`Data='2026-07-31'`).
- O **IBGE responde sempre em gzip**.
- O Olinda às vezes devolve erro **dentro de um comentário `/*{...}*/` com HTTP 200** —
  o sistema detecta isso e trata como falha.
- **CVM fundos**: desde a Resolução CVM 175 (regime FIF), o informe diário identifica
  o fundo pela coluna `CNPJ_FUNDO_CLASSE` (nível classe), enquanto o cadastro `cad_fi`
  usa `CNPJ_FUNDO` (nível fundo). Para fundos de classe única coincidem; para
  multiclasse não. Por isso a tela de fundos aceita digitar o CNPJ da classe direto.
- **DataJud** aceita só POST em `/_search` com a chave pública do CNJ no header
  `Authorization: APIKey ...`; a data de ajuizamento filtra por `range`.
- **ComexStat** só responde a POST, com o recorte no corpo (`flow`, `period`, `details`).
- **Compras.gov.br** exige `tamanhoPagina` entre 10 e 500 — fora disso, HTTP 400.

## 7. Organização do menu e dos departamentos

Os módulos **não** são agrupados pelo órgão que publica o dado, e sim pela
pergunta de negócio de quem usa. Ninguém abre o sistema pensando "quero o Olinda
do Bacen"; pensa "esse credenciado tem impedimento?". Esse critério (`grupo`)
organiza o **menu**.

Separado disso, cada módulo também declara em `core/modulos.py` o campo
`departamentos`: o(s) setor(es) que efetivamente usam aquela tela, a partir da
lista fixa em `DEPARTAMENTOS`. Um módulo pode interessar a mais de um setor (ex.:
"Verificar Credenciado" serve Compliance e Jurídico); um grupo do menu pode
reunir módulos de setores diferentes quando a pergunta de negócio é a mesma
(ex.: *Instituições e Rede* serve Compliance, Comercial e Tesouraria, cada um
com sua tela). Módulo novo sem setor claro fica com `departamentos: []`
(uso geral).

| Grupo (menu) | Módulos | Setor(es) que consome |
|---|---|---|
| **Visão Geral** | Painel Executivo | Diretoria |
| **Indicadores e Mercado** | Séries Econômicas · Expectativas (Focus) · Câmbio (PTAX) · Companhias Abertas e Fundos (CVM) · IF.data · Índices e Reajuste Imobiliário | Tesouraria/Financeiro · Administrativo |
| **Instituições e Rede** | Instituições do SFN · Agências e Postos · Correspondentes | Compliance · Comercial |
| **Compliance e Integridade** | Impedimentos e Penalidades · Domínios Verificados · Verificar Credenciado · Qualidade de Ouvidorias · Portal da Transparência · Investigação/OSINT | Compliance · Jurídico · TI · Auditoria |
| **Pagamentos** | Pix e DICT · SPI e STR · Meios de Pagamento | Tesouraria/Financeiro · Compliance |
| **Tarifas e Produtos** | Tarifas Bancárias · Open Finance | Comercial · Tesouraria/Financeiro · TI |
| **Comércio Exterior** | Balança Comercial · NCM e Tarifa Externa (TEC) | Comercial |
| **Governo e Setor Público** | Contas de Estados e Municípios · Contratações Públicas | Comercial · Compliance · Jurídico |
| **Jurídico e Legislativo** | Processos (DataJud) · Acompanhamento Legislativo · Diários Oficiais | Jurídico |
| **Recursos Humanos** | Indicadores de RH | RH |
| **Território e Economia** | IBGE | uso geral |
| **Consultas Rápidas** | CNPJ · CEP · Bancos · Feriados · CNAE | uso geral · Compliance · Comercial |
| **Administração** | Usuários e Permissões · Auditoria · Fontes de Dados | TI · Auditoria |

Por isso a mesma API aparece em grupos diferentes: `Instituicoes_em_funcionamento`
alimenta tanto o cadastro em *Instituições e Rede* quanto os domínios verificados
em *Compliance*.

Antes essa 2ª tabela existia em duplicidade com uma lista de "departamentos" na
seção 6 e os dois textos podiam ficar dessincronizados. Agora só existe uma
fonte da verdade (`core/modulos.py`); o README é gerado a partir da leitura
desse arquivo e deve ser revisado junto dele quando um módulo mudar de grupo
ou de setor.

Ao criar um usuário em **Administração › Usuários e Permissões**, escolher o
setor e o perfil "Sugerido para o setor" já marca os módulos cadastrados para
aquele departamento — sem precisar catar módulo a módulo pelo menu inteiro. Na
edição de um usuário existente, o botão "Sugerir do setor" faz o mesmo a
qualquer momento.

Para acrescentar um módulo novo, basta adicionar uma entrada em
`core/modulos.py` (com `grupo` e `departamentos`) e criar o arquivo
correspondente em `paginas/` com uma função `render()`. O menu, a tela de
permissões e os perfis sugeridos passam a reconhecê-lo sozinhos.

## 8. Estrutura do projeto

```
Sistema Geral Interdepartamental/
├── app.py                    entrada; monta o menu conforme as permissões
├── requirements.txt
├── .streamlit/config.toml    porta 6789, tema e parâmetros do servidor
├── core/
│   ├── config.py             constantes, prazos de atualização, senha padrão
│   ├── db.py                 SQLite (usuários, permissões, auditoria)
│   ├── security.py           PBKDF2, política de senhas
│   ├── auth.py               login, troca obrigatória, controle de acesso
│   ├── modulos.py            catálogo de módulos = menu + permissões
│   ├── http.py               cliente HTTP, cache em disco, retry, fallback
│   ├── ui.py                 componentes visuais e padrões de UX
│   └── audit.py              trilha de auditoria
├── services/
│   ├── bcb.py                todas as APIs do Banco Central
│   └── externas.py           IBGE, BrasilAPI, Open Finance
├── paginas/                  uma tela por módulo
├── scripts/
│   ├── instalar.ps1          cria o .venv e instala dependências
│   ├── iniciar.ps1 / .bat    sobe o servidor na porta 6789
│   └── atualizar_cache.py    aquecimento opcional via Agendador de Tarefas
└── dados/
    ├── integrapublic.db      usuários, permissões, auditoria
    └── cache/                cópias locais das APIs
```

## 9. Testes

Dois scripts verificam o sistema sem precisar clicar em nada:

```powershell
.\.venv\Scripts\python.exe scripts\autoteste.py
```

Confere as 35 telas (importação), o ciclo de vida de usuário (criação com senha
padrão, permissões, edição, troca de senha, bloqueio por tentativas, exclusão),
a montagem das URLs OData e a disponibilidade das 9 fontes. Roda sobre um banco
temporário — **não toca no banco de produção** e pode ser executado com o sistema
no ar.

```powershell
.\.venv\Scripts\python.exe scripts\teste_paginas.py
```

Executa cada uma das 35 telas de verdade, com chamadas reais às APIs, e falha se
alguma levantar exceção ou renderizar vazia. É o teste que pega erro de coluna,
tipo e widget duplicado.

> Alterou código? **Reinicie o servidor.** O `fileWatcherType = "none"` no
> `config.toml` desliga a recarga automática de propósito — em produção não se
> quer o serviço reiniciando sozinho porque alguém salvou um arquivo.

## 10. Backup

O que precisa de backup é a pasta `dados/`:

- `integrapublic.db` — usuários, permissões e auditoria (**insubstituível**);
- `cache/` — descartável, o sistema reconstrói sozinho.

Com o serviço parado, copiar a pasta basta.

## 11. Problemas comuns

| Sintoma | Causa provável |
|---|---|
| Não abre pela rede, só em `localhost` | Porta 6789 bloqueada no firewall — veja a seção 1 |
| "A porta 6789 já está em uso" | Outra instância aberta; feche o console anterior |
| Tela com aviso "exibindo cópia de..." | A fonte oficial está fora do ar; o dado local continua válido |
| Precisei logar de novo após atualizar a página | Comportamento esperado — a sessão vive na aba (seção 4) |
| Alterei o código e nada mudou | Reinicie o servidor; a recarga automática está desligada (seção 9) |
| Primeira abertura de uma tela demora | Cache frio; agende `atualizar_cache.py` (seção 5) |
| IF.data ou Pix sem dados no período mais recente | Publicação com defasagem; escolha o período anterior |
| Usuário não vê nenhum módulo | Sem permissões atribuídas — libere em Administração |
| Esqueci a senha do admin | Outro administrador pode redefini-la; se não houver, apague `dados/integrapublic.db` (perde usuários e auditoria) e reinicie |
