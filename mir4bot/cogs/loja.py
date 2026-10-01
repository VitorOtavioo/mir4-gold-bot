import discord
from discord import app_commands
from discord.ext import commands

from utils.precificacao import carregar_config, salvar_config, calcular_pedido
from utils.cotacao import obter_cotacao_usd_brl


def eh_staff():
    """Checagem: só quem tem permissão de gerenciar servidor mexe nos preços."""

    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.manage_guild:
            return True
        raise app_commands.CheckFailure(
            "Você não tem permissão para usar este comando."
        )

    return app_commands.check(predicate)


class Loja(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="precos", description="Mostra as faixas de preço do gold MIR4")
    async def precos(self, interaction: discord.Interaction):
        await interaction.response.defer()

        config = carregar_config()
        cotacao = await obter_cotacao_usd_brl(config["cotacao_fallback_usd_brl"])

        embed = discord.Embed(
            title="💰 Preços de Gold — MIR4",
            description=f"Cotação atual: 1 USD ≈ R$ {cotacao:.2f}",
            color=discord.Color.gold(),
        )

        for faixa in config["faixas_brl"]:
            minimo = faixa["min"]
            maximo = faixa["max"]
            preco_brl = faixa["preco"]
            preco_usd = preco_brl / cotacao

            faixa_label = f"{minimo:,}+".replace(",", ".") if maximo is None else (
                f"{minimo:,} - {maximo:,}".replace(",", ".")
            )
            embed.add_field(
                name=f"{faixa_label} Gold",
                value=f"R$ {preco_brl:.2f}/1k  •  $ {preco_usd:.2f}/1k",
                inline=False,
            )

        servidores = config.get("servidores", {})
        if servidores:
            lista = ", ".join(servidores.keys())
            embed.add_field(name="Servidores disponíveis", value=lista, inline=False)

        embed.set_footer(
            text=f"Taxa de mercado do jogo: {config['taxa_mercado_percent']}% (aplicada ao gold enviado)"
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="setfaixa", description="[Staff] Define o preço (R$) de uma faixa de quantidade")
    @app_commands.describe(
        minimo="Quantidade mínima da faixa",
        maximo="Quantidade máxima da faixa (deixe 0 para 'sem limite')",
        preco="Preço em reais por 1000 gold",
    )
    @eh_staff()
    async def setfaixa(
        self, interaction: discord.Interaction, minimo: int, maximo: int, preco: float
    ):
        config = carregar_config()
        faixas = config["faixas_brl"]

        maximo_valor = None if maximo == 0 else maximo
        for faixa in faixas:
            if faixa["min"] == minimo:
                faixa["max"] = maximo_valor
                faixa["preco"] = preco
                break
        else:
            faixas.append({"min": minimo, "max": maximo_valor, "preco": preco})

        faixas.sort(key=lambda f: f["min"])
        config["faixas_brl"] = faixas
        salvar_config(config)

        texto_faixa = f"{minimo}+" if maximo_valor is None else f"{minimo}-{maximo_valor}"
        await interaction.response.send_message(
            f"✅ Faixa **{texto_faixa}** atualizada para **R$ {preco:.2f}**/1k.",
            ephemeral=True,
        )

    @app_commands.command(name="settaxa", description="[Staff] Define a taxa de mercado do jogo (%)")
    @eh_staff()
    async def settaxa(self, interaction: discord.Interaction, percentual: float):
        config = carregar_config()
        config["taxa_mercado_percent"] = percentual
        salvar_config(config)
        await interaction.response.send_message(
            f"✅ Taxa de mercado atualizada para **{percentual}%**.", ephemeral=True
        )

    @setfaixa.error
    @settaxa.error
    async def on_staff_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message(
                "🚫 Você não tem permissão para usar este comando.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"⚠️ Ocorreu um erro: {error}", ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Loja(bot))
