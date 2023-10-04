from src.cobot import COInteraction

async def is_bot_admin(interaction: COInteraction) -> bool:
    """Check if the user is a bot admin."""
    return interaction.user.id in interaction.client.config["ADMIN_IDS"]
