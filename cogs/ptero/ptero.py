# QuantumPterodactyl: A cog which uses Discord Interactions to send commands to the Pterodactyl server API.
#
# Author:
#    Dave Chadwick (github.com/ropeadope62)
#    Patrick Downing (github.com/padraignix)
# Version:
#    0.1

import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import os
from dotenv import load_dotenv
import logging
import time

class QuantumPterodactyl(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # We will use the same logger as we use for the client in QCAdmin loaded cogs
        self.logger = bot.logger
        load_dotenv()
        self.api_key = os.getenv("PTERODACTYL_API_KEY")
        self.panel_url = os.getenv("PTERODACTYL_PANEL_URL")

        if not all([self.api_key, self.panel_url]):
            self.logger.error("Missing required Pterodactyl dotenv variables")
            raise ValueError("Missing required Pterodactyl dotenv variables")

    @app_commands.command(name="pt_commands", description="List all QuantumPterodactyl commands")
    async def list_commands(self, Interaction: discord.Interaction):
        """QuantumPterodactyl command list:"""
        commands_list = [
            "/pt_list - List all Pterodactyl game servers",
            "/pt_power state <serverid:str> - Get the current state of the game server",
            "/pt_power start <serverid:str> - Starts the game server",
            "/pt_power stop <serverid:str> - Stops the game server gracefully",
            "/pt_power restart <serverid:str> - Restarts the game server",
            "/pt_power kill <serverid:str> - Forcefully stops the game server",
            "/pt_commands - Lists all available QuantumPterodactyl commands",
        ]
        commands_message = "\n".join(commands_list)
        await Interaction.response.send_message(f"**QuantumPterodactyl Commands:**\n{commands_message}")
        embed = discord.Embed(
            title="QuantumPterodactyl Commands",
            description="List of all available commands",
            color=discord.Color.purple(),
        )
        for command in commands_list:
            name, description = command.split(" - ")
            embed.add_field(name=name, value=description, inline=False)
        
        await Interaction.response.send_message(embed=embed)

    async def _send_power_signal(self, signal: str, server_id: str) -> tuple[bool, str]:
        """
        Send a power signal to the Quantumly Confused Pterodactyl server.

        Args:
            signal (str): One of 'start', 'stop', 'restart', 'kill'
            server_id (str): The server ID to target for the power signal
        """
        url = f"{self.panel_url}/api/client/servers/{server_id}/power"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        data = {"signal": signal}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=data) as response:
                    if response.status == 204:  # Success with no content
                        self.logger.info(f"Successfully sent {signal} signal to server {server_id}")
                        return (True,f"Successfully sent {signal} signal to server {server_id}",)
                    else:
                        error_text = await response.text()
                        self.logger.error(f"Pterodactyl API error: {error_text}")
                        return (False,f"Failed to send {signal} signal. Status: {response.status}",)
        except Exception as e:
            self.logger.error(f"Error sending power signal to server {server_id}: {str(e)}")
            return False, f"Error occurred: {str(e)}"

    power = app_commands.Group(name="pt_power", description="Control server power state.")

    @power.command(name="start")
    @app_commands.checks.has_permissions(administrator=True)
    async def start_server(self, Interaction: discord.Interaction, server_id: str):
        """Starts the specified game server"""
        await Interaction.response.defer()  # Discord: always defer the response when using Interactions that may take longer than 3 seconds to respond

        success, message = await self._send_power_signal("start", server_id)

        if success:
            await Interaction.followup.send(f"🟢 Server `{server_id}` is starting up...")
            self.logger.info(f"Server `{server_id}` is starting up")
        else:
            await Interaction.followup.send(f"❌ Failed to start server `{server_id}`: {message}")
            self.logger.error(f"Failed to start server `{server_id}`: {message}")

    @power.command(name="stop")
    @app_commands.checks.has_permissions(administrator=True)
    async def stop_server(self, Interaction: discord.Interaction, server_id: str):
        """Stops the specified game server gracefully"""
        await Interaction.response.defer()

        success, message = await self._send_power_signal("stop", server_id)

        if success:
            await Interaction.followup.send(f"🔴 Server `{server_id}` is shutting down...")
            self.logger.info(f"Server `{server_id}` is shutting down")
        else:
            await Interaction.followup.send(f"❌ Failed to stop server `{server_id}`: {message}")
            self.logger.error(f"Failed to stop server `{server_id}`: {message}")

    @power.command(name="restart")
    @app_commands.checks.has_permissions(administrator=True)
    async def restart_server(self, Interaction: discord.Interaction, server_id: str):
        """Restarts the specified game server"""
        await Interaction.response.defer()

        success, message = await self._send_power_signal("restart", server_id)

        if success:
            await Interaction.followup.send(f"🔄 Server `{server_id}` is restarting...")
            self.logger.info(f"Server `{server_id}` is restarting")
        else:
            await Interaction.followup.send(f"❌ Failed to restart server `{server_id}`: {message}")
            self.logger.error(f"Failed to restart server `{server_id}`: {message}")

    @power.command(name="kill")
    @app_commands.checks.has_permissions(administrator=True)
    async def kill_server(self, Interaction: discord.Interaction, server_id: str):
        """Forcefully stops the specified game server"""
        await Interaction.response.defer()

        success, message = await self._send_power_signal("kill", server_id)

        if success:
            await Interaction.followup.send(f"⚠️ Server `{server_id}` has been forcefully stopped!")
            self.logger.warning(f"Server `{server_id}` has been forcefully stopped")
        else:
            await Interaction.followup.send(f"❌ Failed to kill server `{server_id}`: {message}")
            self.logger.error(f"Failed to kill server `{server_id}`: {message}")

    @power.command(name="state")
    @app_commands.checks.has_permissions(administrator=True)
    async def power_state(self, Interaction: discord.Interaction, server_id: str):
        """Fetches and displays the current power state of the specified server"""
        await Interaction.response.defer()

        url = f"{self.panel_url}/api/client/servers/{server_id}/resources"
        self.logger.info(f"Fetching power state from {url}")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        power_state = data.get("attributes", {}).get("current_state", "Unknown")

                        # Send the power state as a message
                        await Interaction.followup.send(f"The current power state of server `{server_id}` is: `{power_state}`")
                        self.logger.info(f"Power state fetched for server `{server_id}`: {power_state}")
                    else:
                        error_text = await response.text()
                        self.logger.error(f"Pterodactyl API error: {error_text}")
                        await Interaction.followup.send(f"❌ Failed to fetch power state. Status: {response.status}")
        except Exception as e:
            self.logger.error(f"Error fetching power state for server `{server_id}`: {str(e)}")
            await Interaction.followup.send(f"❌ Error occurred: {str(e)}")

    #server = app_commands.Group(name="pt_list", description="Server information.")
    #@server.command(name="pt_list", description="List all game servers")
    @app_commands.command(name="pt_list", description="List all QuantumPterodactyl commands")
    @app_commands.checks.has_permissions(administrator=True, manage_guild=True)
    async def list_servers(self, Interaction: discord.Interaction):
        """
        Lists all servers associated with the Pterodactyl panel.
        """
        await Interaction.response.defer()

        url = f"{self.panel_url}/api/application/servers"
        self.logger.info(f"Fetching server list from {url}")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        server_list = []
                        data = await response.json()
                        embed = discord.Embed(title='QC - Server List',colour=436557,)
                        embed.set_image(url='https://i.ibb.co/ZMFzpyD/qcadmin.png')
                        for server in data["data"]:
                            url = f"{self.panel_url}/api/client/servers/{server['attributes']['identifier']}/resources"
                            self.logger.info(f"Fetching list power state from {url}")

                            headers = {
                                "Authorization": f"Bearer {self.api_key}",
                                "Accept": "application/json",
                                "Content-Type": "application/json",
                            }
                            try:
                                async with aiohttp.ClientSession() as session:
                                    async with session.get(url, headers=headers) as response:
                                        if response.status == 200:
                                            data_list = await response.json()
                                            power_state = data_list.get("attributes", {}).get("current_state", "Unknown")
                                            self.logger.info(f"Power state fetched for server `{server}`: {power_state}")
                                        else:
                                            error_text = await response.text()
                                            self.logger.error(f"Pterodactyl API error: {error_text}")
                                            #await Interaction.followup.send(f"❌ Failed to fetch power state. Status: {response.status}")
                            except Exception as e:
                                self.logger.error(f"Error fetching list power state for server `{server_id}`: {str(e)}")
                            embed.add_field(name=f"{server['attributes']['name']}", value=f"{server['attributes']['identifier']} - {power_state}", inline=False)
                        #server_list.append(f"{server['attributes']['name']} | {server['attributes']['identifier']} | {power_state}")
                        
                        await Interaction.followup.send(embed=embed)
                    else:
                        error_text = await response.text()

                        self.logger.error(f"Pterodactyl API error: {error_text}")
                        await Interaction.followup.send(f"❌ Failed to list servers. Status: {response.status}")
        except Exception as e:
            print(f'Error listing servers: {str(e)}')
            self.logger.error(f"Error listing servers: {str(e)}")
            await Interaction.followup.send(f"❌ Error occurred: {str(e)}")

async def setup(bot):
    await bot.add_cog(QuantumPterodactyl(bot))
    bot.logger.info("Cog loaded: QuantumPterodactyl v0.1")