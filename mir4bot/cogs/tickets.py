import asyncio
import io
import logging
import os

import discord
from discord import app_commands
from discord.ext import commands

from utils.precificacao import calcular_pedido

log = logging.getLogger("mir4bot")

STAFF_ROLE_ID = int(os.getenv("STAFF_ROLE_ID", "0"))
TICKET_CATEGORY_ID = int(os.getenv("TICKET_CATEGORY_ID", "0"))
TERMOS_URL = os.getenv("TERMOS_URL", "https://docs.google.com/document/d/SEU-LINK-AQUI/edit")
ARQUIVO_CHANNEL_ID = int(os.getenv("ARQUIVO_CHANNEL_ID", "0"))
MINUTOS_INATIVIDADE = 5


class ModalPedido(discord.ui.Modal, title="Adicionar ao carrinho"):
    quantidade = discord.ui.TextInput(
        label="Quantidade de Gold",
        placeholder="Ex: 1000, 5000, 10000...",
        required=True,
        max_length=10,
    )
    servidor = discord.ui.TextInput(
        label="Servidor",
        placeholder="Ex: SA, NA, EU, ASIA, MENA",
        required=True,
        max_length=50,
    )

    async def on_submit(self, interaction: discord.Interaction):
        texto_qtd = str(self.quantidade.value).strip().replace(".", "").replace(",", "")
        if not texto_qtd.isdigit():
            await interaction.response.send_message(
                "🚫 Digite a quantidade de gold usando apenas números (ex: 1000).",
                ephemeral=True,
            )
            return

        quantidade = int(texto_qtd)

        # Consultar a cotação pode levar um instante, então avisamos o
        # Discord que a resposta vem em seguida (evita "interação falhou").
        await interaction.response.defer(ephemeral=True)

        try:
            pedido = await calcular_pedido(quantidade)
        except ValueError:
            await interaction.followup.send(
                "🚫 Não há faixa de preço cadastrada para essa quantidade. "
                "Fale com a equipe para confirmar o valor.",
                ephemeral=True,
            )
            return

        await criar_ticket(interaction, self, pedido)


async def criar_ticket(interaction: discord.Interaction, dados: ModalPedido, pedido: dict):
    guild = interaction.guild
    autor = interaction.user

    categoria = guild.get_channel(TICKET_CATEGORY_ID) if TICKET_CATEGORY_ID else None
    if categoria is not None and not isinstance(categoria, discord.CategoryChannel):
        log.warning(
            "TICKET_CATEGORY_ID (%s) não é uma categoria válida — criando o "
            "ticket sem categoria. Corrija o valor no .env.",
            TICKET_CATEGORY_ID,
        )
        categoria = None
    staff_role = guild.get_role(STAFF_ROLE_ID) if STAFF_ROLE_ID else None

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        autor: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
    }
    if staff_role:
        overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

    nome_canal = f"ticket-{autor.name}".lower().replace(" ", "-")[:90]

    canal = await guild.create_text_channel(
        name=nome_canal,
        category=categoria,
        overwrites=overwrites,
        reason=f"Ticket de compra aberto por {autor}",
    )

    quantidade_fmt = f"{pedido['quantidade']:,}".replace(",", ".")
    gold_enviar_fmt = f"{pedido['gold_a_enviar']:,}".replace(",", ".")

    embed = discord.Embed(
        title="🛒 Carrinho - MIR4",
        color=discord.Color.blurple(),
    )
    embed.add_field(name="Comprador", value=autor.mention, inline=False)
    embed.add_field(name="🌐 Servidor", value=str(dados.servidor), inline=True)
    embed.add_field(name="🪙 Gold", value=f"{quantidade_fmt} Gold", inline=True)
    embed.add_field(
        name="Preço",
        value=(
            f"$ {pedido['total_usd']:.2f} ≈ R$ {pedido['total_brl']:.2f}\n"
            f"USD: $ {pedido['preco_usd_mil']:.2f}/1k (cotação R$ {pedido['cotacao']:.2f}) | "
            f"BRL: R$ {pedido['preco_brl_mil']:.2f}/1k"
        ),
        inline=False,
    )
    embed.add_field(
        name=f"💰 Total com taxa ({pedido['taxa_percent']}%)",
        value=f"{gold_enviar_fmt} Gold (a enviar para o cliente)",
        inline=False,
    )
    embed.add_field(name="💵 Total em USD", value=f"$ {pedido['total_usd']:.2f}", inline=True)
    embed.add_field(name="💴 Total em BRL", value=f"R$ {pedido['total_brl']:.2f}", inline=True)
    embed.set_footer(text="Aguarde um atendente para confirmar o pagamento e a entrega.")

    mencao_staff = staff_role.mention if staff_role else "equipe"
    view_carrinho = ViewCarrinho(pedido, autor.id)
    await canal.send(
        content=f"{autor.mention} {mencao_staff}",
        embed=embed,
        view=view_carrinho,
    )

    interaction.client.loop.create_task(
        verificar_inatividade(canal, view_carrinho)
    )

    await interaction.followup.send(
        f"✅ Ticket criado: {canal.mention}", ephemeral=True
    )


async def verificar_inatividade(canal: discord.TextChannel, view_carrinho: "ViewCarrinho"):
    """Se o cliente ficar parado no carrinho por muito tempo, manda uma
    mensagem perguntando se ele precisa de ajuda."""
    await asyncio.sleep(MINUTOS_INATIVIDADE * 60)

    if view_carrinho.prosseguiu or view_carrinho.fechado:
        return

    embed = discord.Embed(
        title="💖 Precisando de Ajuda?",
        description="Oii, Precisa de alguma ajuda com seu pedido? 💖",
        color=discord.Color.from_rgb(237, 88, 130),
    )
    try:
        await canal.send(embed=embed, view=ViewAjuda())
    except discord.HTTPException:
        # Canal já foi fechado/apagado nesse meio tempo — não tem problema.
        pass


class ViewAjuda(discord.ui.View):
    """Botões enviados quando o cliente demora para avançar no pedido."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Sim, preciso de ajuda!", style=discord.ButtonStyle.danger, emoji="🆘")
    async def sim(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)

        guild = interaction.guild
        staff_role = guild.get_role(STAFF_ROLE_ID) if STAFF_ROLE_ID else None
        mencao_staff = staff_role.mention if staff_role else "equipe"
        await interaction.channel.send(
            f"🆘 {interaction.user.mention} pediu ajuda com o pedido! {mencao_staff}"
        )

    @discord.ui.button(label="Não, está tudo bem.", style=discord.ButtonStyle.success, emoji="✅")
    async def nao(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)


class ViewCarrinho(discord.ui.View):
    """Botões dentro do carrinho: seguir para pagamento ou fechar o ticket."""

    def __init__(self, pedido: dict, comprador_id: int):
        super().__init__(timeout=None)
        self.pedido = pedido
        self.comprador_id = comprador_id
        self.prosseguiu = False
        self.fechado = False

    @discord.ui.button(label="Prosseguir para o pagamento", style=discord.ButtonStyle.primary, emoji="💳")
    async def prosseguir(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.prosseguiu = True
        embed = discord.Embed(title="💳 Formas de Pagamento", color=discord.Color.blurple())
        embed.add_field(name="Jogo", value="MIR4", inline=False)
        embed.add_field(
            name="Total",
            value=f"$ {self.pedido['total_usd']:.2f} | R$ {self.pedido['total_brl']:.2f}",
            inline=False,
        )
        embed.description = (
            "Selecione a forma de pagamento desejada:\n\n"
            "⚠️ Ao fazer uma compra conosco, você declara que leu e concorda "
            f"com nossos termos de uso:\n[📄 termos-de-uso-e-politicas]({TERMOS_URL})"
        )
        await interaction.response.send_message(embed=embed, view=ViewFormasPagamento(self.pedido, self.comprador_id))

    @discord.ui.button(label="Fechar Ticket", style=discord.ButtonStyle.danger, custom_id="fechar_ticket")
    async def fechar(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.fechado = True
        await _fechar_ticket(interaction)


class ViewFormasPagamento(discord.ui.View):
    """Botões de forma de pagamento: só avisam a equipe, sem enviar dados automaticamente."""

    def __init__(self, pedido: dict, comprador_id: int):
        super().__init__(timeout=None)
        self.pedido = pedido
        self.comprador_id = comprador_id

    async def _selecionar(self, interaction: discord.Interaction, nome: str):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.channel.send(
            f"💳 {interaction.user.mention} escolheu pagar via **{nome}**. "
            f"Equipe, por favor envie os dados de pagamento."
        )
        await interaction.channel.send(
            "Quando o pagamento cair, clique abaixo para confirmar:",
            view=ViewConfirmarPagamento(self.pedido, self.comprador_id),
        )

    @discord.ui.button(label="PIX", style=discord.ButtonStyle.success, emoji="🇧🇷")
    async def pix(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._selecionar(interaction, "PIX")

    @discord.ui.button(label="Binance", style=discord.ButtonStyle.primary, emoji="🟡")
    async def binance(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._selecionar(interaction, "Binance Pay (USDT)")

    @discord.ui.button(label="Voltar", style=discord.ButtonStyle.secondary)
    async def voltar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()


class ViewConfirmarPagamento(discord.ui.View):
    """Botão de staff para confirmar que o pagamento caiu e mandar as
    instruções de entrega (encantamento + prints) pro cliente."""

    def __init__(self, pedido: dict, comprador_id: int):
        super().__init__(timeout=None)
        self.pedido = pedido
        self.comprador_id = comprador_id

    @discord.ui.button(label="Confirmar Pagamento", style=discord.ButtonStyle.success, emoji="✅")
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        tem_permissao = interaction.user.guild_permissions.manage_channels or (
            STAFF_ROLE_ID and any(r.id == STAFF_ROLE_ID for r in interaction.user.roles)
        )
        if not tem_permissao:
            await interaction.response.send_message(
                "🚫 Só a equipe pode confirmar o pagamento.", ephemeral=True
            )
            return

        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)

        gold_fmt = f"{self.pedido['gold_a_enviar']:,}".replace(",", ".")
        instrucoes = (
            f"Colocar um equipamento+5 por {gold_fmt} Gold encanta e printa "
            "encantamento, preciso de 2 print, uma do encantamento, e outra "
            "do item em registro de venda pendente."
        )
        await interaction.channel.send(
            f"✅ Pagamento confirmado por {interaction.user.mention}!\n\n{instrucoes}"
        )
        await interaction.channel.send(
            "Quando os 2 prints forem enviados, clique abaixo para confirmar "
            "que o item está no mercado do jogo:",
            view=ViewConfirmarItemMercado(self.comprador_id),
        )


class ViewConfirmarItemMercado(discord.ui.View):
    """Botão para confirmar que o item já está listado no mercado do jogo,
    depois de conferir os prints. Pode ser clicado pela staff OU pelo
    próprio cliente que abriu o ticket."""

    def __init__(self, comprador_id: int):
        super().__init__(timeout=None)
        self.comprador_id = comprador_id

    @discord.ui.button(label="Confirmar Item no Mercado", style=discord.ButtonStyle.success, emoji="📦")
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        eh_staff = interaction.user.guild_permissions.manage_channels or (
            STAFF_ROLE_ID and any(r.id == STAFF_ROLE_ID for r in interaction.user.roles)
        )
        eh_comprador = interaction.user.id == self.comprador_id
        if not (eh_staff or eh_comprador):
            await interaction.response.send_message(
                "🚫 Só a equipe ou o cliente do pedido podem confirmar isso.",
                ephemeral=True,
            )
            return

        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)

        await interaction.channel.send(
            f"📦 Item confirmado no mercado por {interaction.user.mention}! "
            "Prosseguindo com a compra do item para concluir a entrega."
        )


async def gerar_transcript(canal: discord.TextChannel) -> discord.File:
    """Baixa todo o histórico do canal e monta um arquivo .txt de transcript."""
    linhas = []
    async for msg in canal.history(limit=None, oldest_first=True):
        hora = msg.created_at.strftime("%d/%m/%Y %H:%M")
        conteudo = msg.content or ""

        for emb in msg.embeds:
            partes = []
            if emb.title:
                partes.append(f"[{emb.title}]")
            if emb.description:
                partes.append(emb.description)
            for campo in emb.fields:
                partes.append(f"{campo.name}: {campo.value}")
            if partes:
                conteudo += ("\n" if conteudo else "") + "\n".join(partes)

        if msg.attachments:
            anexos = ", ".join(a.url for a in msg.attachments)
            conteudo += (f"\n[anexos: {anexos}]" if conteudo else f"[anexos: {anexos}]")

        linhas.append(f"[{hora}] {msg.author}: {conteudo}")

    texto = "\n".join(linhas) if linhas else "(sem mensagens)"
    buffer = io.BytesIO(texto.encode("utf-8"))
    return discord.File(buffer, filename=f"transcript-{canal.name}.txt")


async def arquivar_ticket(canal: discord.TextChannel, guild: discord.Guild, fechado_por: discord.abc.User):
    """Manda o histórico do ticket para o canal de arquivo e apaga o canal."""
    arquivo_canal = guild.get_channel(ARQUIVO_CHANNEL_ID) if ARQUIVO_CHANNEL_ID else None

    if arquivo_canal is None:
        log.warning(
            "ARQUIVO_CHANNEL_ID não configurado (ou inválido) — o ticket %s "
            "foi fechado sem gerar arquivo. Configure no .env.",
            canal.name,
        )
    else:
        try:
            transcript = await gerar_transcript(canal)
            embed = discord.Embed(
                title="🗂️ Ticket arquivado",
                description=f"Canal: **#{canal.name}**\nFechado por: {fechado_por.mention}",
                color=discord.Color.dark_grey(),
                timestamp=discord.utils.utcnow(),
            )
            await arquivo_canal.send(embed=embed, file=transcript)
        except discord.HTTPException as exc:
            log.warning("Falha ao enviar transcript do ticket %s: %s", canal.name, exc)

    try:
        await canal.delete(reason=f"Ticket fechado por {fechado_por}")
    except discord.NotFound:
        pass


async def _fechar_ticket(interaction: discord.Interaction):
    tem_permissao = interaction.user.guild_permissions.manage_channels or (
        STAFF_ROLE_ID and any(r.id == STAFF_ROLE_ID for r in interaction.user.roles)
    )
    if not tem_permissao:
        await interaction.response.send_message(
            "🚫 Só a equipe pode fechar o ticket.", ephemeral=True
        )
        return

    await interaction.response.send_message(
        "📝 Preparando a preservação final do histórico e dos anexos..."
    )
    await asyncio.sleep(2)
    await interaction.channel.send("🔒 Arquivando e fechando tópico em 3 segundos...")
    await asyncio.sleep(3)
    await arquivar_ticket(interaction.channel, interaction.guild, interaction.user)


class ViewFecharTicket(discord.ui.View):
    """Botão fixo dentro de cada ticket para a staff encerrar o atendimento."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Fechar Ticket", style=discord.ButtonStyle.danger, custom_id="fechar_ticket")
    async def fechar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _fechar_ticket(interaction)


class ViewPainel(discord.ui.View):
    """Botão fixo no painel público que qualquer usuário usa para iniciar uma compra."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Comprar Gold",
        style=discord.ButtonStyle.success,
        emoji="🛒",
        custom_id="abrir_ticket_compra",
    )
    async def comprar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModalPedido())


class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Registra as views sem timeout para que os botões continuem
        # funcionando mesmo depois de reiniciar o bot.
        bot.add_view(ViewPainel())
        bot.add_view(ViewFecharTicket())

    @app_commands.command(name="painel", description="[Staff] Publica o painel de compra de gold neste canal")
    async def painel(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "🚫 Você não tem permissão para usar este comando.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="🛒 Loja de Gold — MIR4",
            description=(
                "Clique no botão abaixo para abrir um ticket de compra.\n"
                "Use `/precos` para ver os valores atualizados antes de comprar."
            ),
            color=discord.Color.green(),
        )
        await interaction.channel.send(embed=embed, view=ViewPainel())
        await interaction.response.send_message("✅ Painel publicado!", ephemeral=True)

    @app_commands.command(name="comprar", description="Abre um ticket de compra de gold diretamente")
    async def comprar(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ModalPedido())

    @commands.command(name="f")
    async def fechar_prefixo(self, ctx: commands.Context):
        """!f — fecha e arquiva o ticket. Só administradores podem usar."""
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("🚫 Apenas administradores podem usar esse comando.")
            return

        if ARQUIVO_CHANNEL_ID and ctx.channel.id == ARQUIVO_CHANNEL_ID:
            await ctx.send("🚫 Este comando não pode ser usado no canal de arquivo.")
            return

        await ctx.send("📝 Preparando a preservação final do histórico e dos anexos...")
        await asyncio.sleep(2)
        await ctx.send("🔒 Arquivando e fechando tópico em 3 segundos...")
        await asyncio.sleep(3)
        await arquivar_ticket(ctx.channel, ctx.guild, ctx.author)


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))