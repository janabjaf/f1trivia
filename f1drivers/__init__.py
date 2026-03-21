from .f1drivers import F1Drivers

async def setup(bot):
    await bot.add_cog(F1Drivers(bot))
