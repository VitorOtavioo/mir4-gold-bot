import os
import logging

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("mir4bot")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


@bot.event
async def on_ready():
    log.info(f"Bot conectado como {bot.user} (ID: {bot.user.id})")

    # Sincroniza os comandos de barra (/) apenas com o servidor configurado,
    # o que faz eles aparecerem quase instantaneamente (em vez de até 1h globalmente).
    if GUILD_ID:
        guild = discord.Object(id=GUILD_ID)
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        log.info(f"{len(synced)} comandos sincronizados no servidor {GUILD_ID}")
    else:
        synced = await bot.tree.sync()
        log.info(f"{len(synced)} comandos sincronizados globalmente")

    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching, name="venda de gold MIR4"
        )
    )


async def load_extensions():
    await bot.load_extension("cogs.loja")
    await bot.load_extension("cogs.tickets")


@bot.event
async def setup_hook_replacement():
    pass


async def main():
    async with bot:
        await load_extensions()
        await bot.start(TOKEN)


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit(
            "DISCORD_TOKEN não encontrado. Copie .env.example para .env e "
            "preencha com o token do seu bot."
        )
    import asyncio

    asyncio.run(main())
