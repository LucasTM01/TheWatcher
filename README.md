# 👁️ TheWatcher — Monitor de Divulgações

Sistema que fica de olho em divulgações de associações setoriais, órgãos de
governo e CVM, e **avisa por e-mail e Telegram assim que sai algo novo**.
Silêncio é o estado normal: se nada novo saiu, nada é enviado.

| Fonte | O que monitora |
|---|---|
| Fabus | Produção mensal das associadas (PDF) |
| Fenabrave | Emplacamentos mensais |
| Anfavea | Materiais da coletiva de imprensa mensal |
| ACEA | Emplacamentos na Europa (carros mensal, comerciais trimestral) |
| IATA | Air Passenger / Air Cargo Market Analysis |
| Anfir | Dados do setor (implementos rodoviários) |
| Secex | Balança comercial semanal (até o dia 15) |
| CONAB | Boletim Logístico + Boletim da Safra de Grãos |
| ANTT | Novo CSV mensal do Monitriip (bilhetes de passagem) |
| CVM | **Documentos novos por empresa** (11 empresas, throttle de 2h) |

---

## 1. Instalação (uma vez)

1. Tenha o **Python 3.12+** instalado (já confirmado nesta máquina).
2. Dê dois cliques em **`instalar.bat`** — cria o ambiente virtual, instala as
   dependências e gera os arquivos locais `.env` e `config/global.yaml`
   (a partir dos modelos `.env.example` e `config/global.example.yaml`).
3. Configure os segredos e o Telegram (seções 2 e 3 abaixo). Os destinatários
   de e-mail e o `chat_id` ficam em `config/global.yaml` (ou na aba **Config
   global** do painel).

> **Privacidade:** `.env` e `config/global.yaml` guardam seus segredos e dados
> pessoais (senha, token, e-mails, chat_id) e **não** são versionados (estão no
> `.gitignore`). Ao subir para o GitHub, só vão os modelos `*.example.*` — os
> seus dados reais ficam apenas na sua máquina.

## 2. E-mail (Gmail) — senha de app

O sistema envia e-mails pela sua conta Gmail usando uma **senha de app**
(NÃO é a sua senha normal; é uma senha de 16 letras específica para o sistema):

1. Acesse https://myaccount.google.com/security e ative a
   **verificação em duas etapas** (obrigatória para senhas de app).
2. Acesse https://myaccount.google.com/apppasswords
3. Em "Nome do app", digite `TheWatcher` e clique em **Criar**.
4. Copie a senha de 16 letras exibida (sem os espaços).
5. Abra o arquivo **`.env`** (na pasta do projeto, com o Bloco de Notas) e
   preencha:
   ```
   SMTP_PASSWORD=abcdwxyzabcdwxyz
   ```

Remetente e destinatários ficam em `config/global.yaml` (seção `email:`) —
ou na aba **Config global** do painel.

## 3. Telegram — criar bot, grupo e obter o chat_id

1. **Criar o bot**: no Telegram, fale com **@BotFather** → comando `/newbot`
   → dê um nome (ex.: `TheWatcher Alertas`) e um username terminado em "bot"
   (ex.: `thewatcher_lucas_bot`). O BotFather responde com o **token**
   (algo como `1234567890:AAExemplo...`).
2. Abra o arquivo **`.env`** e preencha:
   ```
   TELEGRAM_BOT_TOKEN=1234567890:AAExemplo...
   ```
3. **Criar o grupo**: crie um grupo no Telegram (ex.: "Divulgações") e
   **adicione o bot** como membro.
4. **Obter o chat_id do grupo**: envie qualquer mensagem no grupo (ex.:
   "oi"), depois abra no navegador (trocando `SEU_TOKEN` pelo token):
   ```
   https://api.telegram.org/botSEU_TOKEN/getUpdates
   ```
   Procure por `"chat":{"id":-100123456789` — esse número **negativo** é o
   chat_id do grupo.
5. Preencha o chat_id em `config/global.yaml` (seção `telegram:`) ou na aba
   **Config global** do painel.

> Se o `getUpdates` voltar vazio: remova o bot do grupo, adicione de novo e
> mande outra mensagem. Se o grupo virar supergrupo, o id muda (começa com
> `-100...`) — repita o passo 4.

## 4. Painel (front-end)

Dois cliques em **`abrir_painel.bat`** — o navegador abre sozinho em
`http://127.0.0.1:8765`. A janela preta precisa ficar aberta enquanto o
painel estiver em uso.

No painel você consegue:

- **Submódulos**: ver todas as fontes com status (ativa, última checagem,
  última divulgação detectada, "rodaria/pularia agora e por quê"),
  ligar/desligar cada fonte com um clique e **editar as restrições**
  (janela de dias, throttle, canais, título do alerta etc.) sem mexer em
  código.
- **Checar agora**: força a checagem de uma fonte ou de todas
  (ignora janela/throttle/já-saiu). Itens já conhecidos **não** são
  reenviados. O botão **"teste envio"** reenvia o último item conhecido —
  útil para testar e-mail/Telegram de ponta a ponta.
- **Logs**: o que rodou, o que pulou (e por quê), o que falhou.
- **Mensagens**: histórico de tudo que foi enviado (e falhas de envio).
- **Estatísticas**: checagens, alertas, taxa de falha e duração por fonte.

## 5. Linha de comando (opcional)

```
.venv\Scripts\python.exe -m watcher run                  # ciclo normal
.venv\Scripts\python.exe -m watcher run --force          # ignora restrições
.venv\Scripts\python.exe -m watcher run --force --dry-run  # testa sem enviar/gravar
.venv\Scripts\python.exe -m watcher run --force --resend --source fabus  # teste de envio
.venv\Scripts\python.exe -m watcher run --source cvm     # só uma fonte
.venv\Scripts\python.exe -m watcher list                 # situação de cada fonte
.venv\Scripts\python.exe -m watcher panel                # painel web
```

## 6. Agendamento no Task Scheduler (seg–sex, 7h à meia-noite, a cada 1h)

O motor é o **`run_watcher.bat`** — ele roda um ciclo e encerra. A tarefa
roda na conta **SYSTEM**, ou seja: funciona **logada ou não** e **sem
precisar de senha**. (Foi a escolha certa aqui porque a conta é Microsoft
com login por PIN — o agendamento com senha não aceitaria o PIN.)

**Opção A — recomendada (arquivo .bat, mais fácil):**

1. Clique com o **botão direito** em **`agendar_tarefa.bat`** →
   **"Executar como administrador"**.
2. Aceite o aviso do Windows (UAC). **Não pede senha.**
3. A janela mostra "SUCESSO" e o agendamento, e **fica aberta** até você
   apertar uma tecla (assim você lê o resultado ou o erro, se houver).

Para **remover** depois: clique com o botão direito em
`remover_tarefa.bat` → "Executar como administrador" (ou rode
`schtasks /Delete /TN "TheWatcher" /F` num PowerShell de administrador).

**Opção B — comando manual** (PowerShell aberto **como administrador**):

```
schtasks /Create /TN "TheWatcher" /TR "\"C:\Users\lucas\PycharmProjects\TheWatcher\run_watcher.bat\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 07:00 /RI 60 /DU 17:00 /RU SYSTEM /RL HIGHEST /F
```

Detalhes: `/SC WEEKLY /D MON,TUE,WED,THU,FRI` = só dias úteis;
`/ST 07:00` = começa às 7h; `/RI 60` = repete a cada 1 hora; `/DU 17:00` =
durante 17 horas (logo, até a meia-noite); `/RU SYSTEM` = roda deslogada, sem
senha. Para mudar o horário, ajuste `/ST` e `/DU`. (Os nomes dos dias seguem
o idioma do Windows — nesta máquina, en-US, são MON/TUE/...; em Windows
português seriam SEG/TER/...)

Conferir: `schtasks /Query /TN "TheWatcher" /V /FO LIST`

**Opção C — pela interface gráfica (mais controle):**

1. Abra o **Agendador de Tarefas** (Task Scheduler) → "Criar Tarefa…".
2. Aba **Geral**: nome `TheWatcher`; marque **"Executar estando o usuário
   conectado ou não"** (vai rodar deslogada — o Windows pode pedir sua senha);
   marque "Executar com privilégios mais altos".
3. Aba **Disparadores** → Novo:
   - "Iniciar a tarefa": Conforme um agendamento → **Semanalmente**;
   - marque **seg, ter, qua, qui, sex**; "Iniciar" às **07:00**;
   - em **Configurações avançadas**: marque "Repetir a tarefa a cada"
     **1 hora**, "durante" **17 horas**.
4. Aba **Ações** → Nova: "Iniciar um programa" →
   `C:\Users\lucas\PycharmProjects\TheWatcher\run_watcher.bat`
   e em "Iniciar em (opcional)": `C:\Users\lucas\PycharmProjects\TheWatcher`
5. Aba **Configurações**: marque "Executar a tarefa o mais rápido possível
   após uma inicialização agendada perdida"; em "Se a tarefa já estiver em
   execução": **Não iniciar uma nova instância**.

> **Teste depois de criar:** abra o Agendador de Tarefas, ache `TheWatcher`,
> clique com o botão direito → **Executar**, e confira a aba **Logs** do
> painel para garantir que a checagem rodou na conta SYSTEM como esperado.

> As janelas de dias e o throttle são responsabilidade do sistema, não do
> agendador: pode disparar de 30 em 30 min o dia todo que cada fonte decide
> sozinha se deve rodar. Há também uma trava (lock) contra execuções
> sobrepostas.

## 7. Como funciona a detecção (resumo)

- **Estado persistente** em `data/state.db` (SQLite): o sistema lembra o que
  já viu entre execuções. Cada item tem uma **chave estável** (protocolo CVM,
  nome de arquivo, URL da publicação) — mudanças cosméticas de layout não
  geram alerta falso.
- **Primeira execução de uma fonte** = "baseline": tudo que já está publicado
  é registrado como visto, **sem alertar** (senão choveria alerta antigo).
  A partir daí, só novidade real dispara mensagem.
- **Parar quando já saiu**: fontes mensais com essa marcação param de checar
  no período corrente após a detecção (a janela 25→5 da IATA cruza o mês e é
  tratada). Secex/CONAB/CVM avisam sempre que houver item novo.
- **Throttle (CVM = 2h)**: o intervalo conta a partir da última checagem
  **efetiva** registrada no banco — sobrevive a reinícios. Execuções dentro
  do intervalo são puladas e logadas como `throttle`.
- **Falha de fonte** (site fora, layout mudou) é isolada: vira `ERRO` no log
  e no painel, **não** derruba as outras fontes nem gera alerta falso. Após
  **3 falhas consecutivas** (configurável), você recebe um aviso de
  manutenção — diferente de alerta de divulgação.
- **Envio falhou?** O item fica marcado como pendente e o envio é tentado de
  novo no ciclo seguinte (não se perde alerta por instabilidade de rede).

## 8. Estrutura de arquivos

```
TheWatcher/
├── instalar.bat          # instala (uma vez)
├── abrir_painel.bat      # abre o painel no navegador
├── run_watcher.bat       # motor headless (Task Scheduler)
├── .env                  # SEGREDOS (senha de app + token do bot) — não compartilhar
├── config/
│   ├── global.yaml       # e-mail, telegram, http, painel
│   └── sources.yaml      # configuração de cada fonte (editável pelo painel)
├── data/
│   ├── state.db          # estado persistente (itens vistos, logs, histórico)
│   └── logs/watcher.log  # log de texto detalhado
└── watcher/              # código (engine, gate, fontes, alertas, painel)
```

## 9. Perguntas frequentes / problemas

**Quero mudar a janela de dias ou desligar uma fonte.**
Painel → clique no nome da fonte → edite → Salvar. (Ou edite
`config/sources.yaml` num editor de texto.)

**Quero filtrar quais documentos da CVM geram alerta.**
`config/sources.yaml` → fonte `cvm` → `params.categories`. Lista vazia = todos.
Ex.: `categories: ["Fato Relevante", "Comunicado ao Mercado"]`.
Para mudar as empresas, edite `params.companies` (código CVM + nome).

**Anfir e o ano.** A URL usa o ano corrente automaticamente; em jan/fev o ano
anterior também é consultado (dado de dezembro sai no ano seguinte).

**E-mail não envia.** Confira: `.env` com `SMTP_PASSWORD` (senha de app, sem
espaços), verificação em 2 etapas ativa no Google, e remetente/destinatários
na Config global. O erro exato aparece em **Mensagens** (painel).

**Telegram não envia.** Confira o token no `.env`, o chat_id (negativo, de
grupo) na Config global e se o bot ainda é membro do grupo.

**Site da Secex caiu / erro de TLS.** O sistema usa o repositório de
certificados do próprio Windows (pacote `truststore`) e baixa a página por
fatias — quedas de conexão são re-tentadas sozinhas.

**A fonte X quebrou (layout mudou).** Ela aparece em vermelho nos Logs e, na
3ª falha seguida, você recebe um aviso. As demais seguem normais. O ajuste é
pontual no módulo da fonte (`watcher/sources/x.py`).

**Fallback da CVM.** Se a consulta ENET (tempo quase real) falhar, o sistema
tenta automaticamente o dataset aberto IPE em `dados.cvm.gov.br`
(atualização semanal — melhor que ficar cego). O alerta indica quando veio
do fallback.

**Adicionar uma fonte nova.** Criar `watcher/sources/minhafonte.py` com uma
função `fetch()` (modelo em `base.py`), registrá-la em
`watcher/sources/__init__.py` e adicionar um bloco em `config/sources.yaml`.
