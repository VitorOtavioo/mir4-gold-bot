# Bot de Venda de Gold — MIR4

Bot em Discord (Python / discord.py) para divulgar preços e gerenciar
vendas de gold do jogo MIR4 através de um **sistema de tickets**
(atendimento manual da sua equipe).

## O que ele faz

- `/precos` — mostra os preços e estoque de gold por servidor do jogo.
- `/painel` — publica um painel com botão **"Comprar Gold"** no canal (staff).
- Ao clicar no botão (ou usar `/comprar`), o usuário preenche um formulário
  (servidor, quantidade, personagem, observações) e o bot cria
  automaticamente um **canal privado de ticket** só visível para ele e a
  equipe de vendas.
- Se o cliente ficar **5 minutos parado** no carrinho sem clicar em
  "Prosseguir para o pagamento", o bot manda uma mensagem perguntando se ele
  precisa de ajuda (com botões Sim/Não que avisam a equipe se ele pedir).
- Dentro do ticket, a staff negocia, confirma pagamento e entrega manualmente.
- Fechamento do ticket, por dois caminhos:
  - Botão **"Fechar Ticket"** (staff com cargo configurado ou permissão de gerenciar canais).
  - Comando **`!f`** digitado no canal do ticket — **só administradores do
    servidor** podem usar.
  - Nos dois casos, o bot gera um arquivo `.txt` com todo o histórico da
    conversa e manda pro canal de arquivo (`ARQUIVO_CHANNEL_ID`), depois
    apaga o canal do ticket.
- `/setpreco` e `/setestoque` — comandos de staff para atualizar preços e
  estoque sem mexer em código.

## 1. Criar o bot no Discord

1. Acesse https://discord.com/developers/applications e clique em **New Application**.
2. Vá em **Bot** → **Add Bot**.
3. Em **Privileged Gateway Intents**, ative **Server Members Intent** e
   **Message Content Intent**.
4. Copie o **Token** (botão "Reset Token" se necessário) — você vai usá-lo no `.env`.
5. Vá em **OAuth2 → URL Generator**, marque o escopo `bot` e `applications.commands`,
   e nas permissões marque: `Manage Channels`, `Send Messages`, `Embed Links`,
   `Read Message History`, `Use Slash Commands`.
6. Abra o link gerado e adicione o bot ao seu servidor.

## 2. Configurar o projeto

```bash
cd mir4bot
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Edite o `.env` com:
- `DISCORD_TOKEN`: o token copiado no passo anterior.
- `GUILD_ID`: ID do seu servidor.
- `STAFF_ROLE_ID`: ID do cargo da sua equipe de vendas.
- `TICKET_CATEGORY_ID`: ID de uma categoria onde os tickets serão criados
  (crie uma categoria chamada, por exemplo, "Tickets" e copie o ID dela).
- `ARQUIVO_CHANNEL_ID`: ID de um canal (ex: `#tickets-arquivados`) que só a
  staff vê, onde o histórico de cada ticket fechado é enviado como arquivo.
- `PAINEL_CHANNEL_ID`: (opcional, informativo — o painel é publicado via
  comando `/painel` no canal onde você digitar o comando).

> Para copiar IDs: Configurações do Discord → Avançado → ative **Modo Desenvolvedor**.
> Depois clique com o botão direito no servidor/canal/cargo → **Copiar ID**.

## 3. Editar preços

Edite `data/precos.json` com os servidores reais do jogo, ou use os comandos
`/setpreco` e `/setestoque` depois que o bot estiver online.

## 4. Rodar o bot

```bash
python main.py
```

## 5. Usar

1. No servidor, vá até o canal de vendas e digite `/painel`.
2. O painel com o botão "Comprar Gold" será publicado.
3. Quando alguém comprar, um ticket privado é criado automaticamente e a
   equipe é notificada.

## Hospedagem 24/7

Para o bot ficar online o tempo todo, hospede em uma VPS (ex: um servidor
Linux barato) ou serviços como Railway/Render, sempre rodando `python main.py`
como um processo persistente (ex: com `systemd`, `pm2` ou `screen`/`tmux`).

## Segurança

- **Nunca** compartilhe seu `DISCORD_TOKEN` nem suba o arquivo `.env` para
  repositórios públicos (o `.gitignore` abaixo já cobre isso).
- Este bot só organiza o atendimento (tickets) — ele **não processa
  pagamentos**. Combine e confirme o pagamento manualmente com o cliente
  dentro do ticket antes de entregar o gold.
