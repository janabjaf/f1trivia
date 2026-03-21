from .nbaplayers import NBARoster

async def setup(bot):
    await bot.add_cog(NBARoster(bot))
