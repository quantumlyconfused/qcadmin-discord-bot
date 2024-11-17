# GitMonitor: A cog which interacts with the GitHub API to notify a Discord channel when a commit is made to one or more repositories. Commit notification is the first feature of the GitMonitor cog, with additional features to be added in the future.
#
# Author:
#    Dave Chadwick (github.com/ropeadope62)
# Version:
#    0.1

import discord
from discord.ext import commands, tasks
import aiohttp
import json
import os

from dotenv import load_dotenv

load_dotenv()

class GitMonitor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = bot.logger
        self.session = aiohttp.ClientSession()
        self.config = self.load_config()
        self.commit_check_loop.start()
        self.api_key = os.getenv('GITMONITOR_TOKEN')
        

    # Close the aiohttp session when the cog is unloaded. 
    def cog_unload(self):
        self.commit_check_loop.cancel()
        self.bot.loop.create_task(self.session.close())
        print("GitMonitor cog unloaded. HTTP session closed.") #! Debug print
        self.logger.info("GitMonitor cog unloaded. HTTP session closed.")
        

    # Load and save configuration
    def load_config(self):
        CONFIG_FILE = "config/gitmonitor_config.json"
        try: 
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
            print(f'Configuration file loaded: {CONFIG_FILE}') #! Debug print
        except FileNotFoundError as e:
            print(f'Configuration file not found: {e}') #! Debug print
            self.logger.error(f"Configuration file not found: {e}")
            return {}


    def save_config(self):
        CONFIG_FILE = "config/gitmonitor_config.json"
        try: 
            with open(CONFIG_FILE, "w") as f:
                json.dump(self.config, f, indent=4)
            print(f"Configuration saved to {CONFIG_FILE}") #! Debug print
            self.logger.info(f"Configuration saved to {CONFIG_FILE}")
        except Exception as e:
            print(f"Error saving configuration: {e}") #! Debug print
            self.logger.error(f"Error saving configuration")
        

    # Background commit checking loop which interacts with the GitHub API. 
    # The loop runs the check_guild_repos coroutine every 10 minutes, which in turn calls the check_repo_commits coroutine.
    @tasks.loop(minutes=10.0)
    async def commit_check_loop(self):
        print("Commit check task started.") #! Debug print
        self.logger.debug("Commit check task started.")
        for guild_id, guild_data in self.data.items():
            print(f"Checking commits for {guild_id}") #! Debug print
            self.logger.debug(f"Checking commits for {guild_id}")
            await self.check_guild_repos(guild_id, guild_data)

    async def check_guild_repos(self, guild_id, guild_data):
        print(f"Checking repos for {guild_id}") #! Debug print
        self.logger.debug(f"Checking repos for {guild_id}")
        if not self.api_key:
            print("No API key found. Exiting.") #! Debug print
            self.logger.debug("No API key found. Exiting.")
            return
        for repo_name, repo_data in guild_data.get("watchlist", {}).items():
            print(f"Checking {repo_name} for commits") #! Debug print
            self.logger.debug(f"Checking {repo_name} for commits")
            await self.check_repo_commits(guild_id, self.api_key, repo_name, repo_data)

    async def check_repo_commits(self, guild_id, api_key, repo_name, repo_data):
        print(f"Check if {repo_name} monitoring is enabled") #! Debug print
        self.logger.debug(f"Check if {repo_name} monitoring is enabled")
        if not repo_data["enabled"]:
            print(f"{repo_name} monitoring is disabled. Skipping.") #! Debug print
            self.logger.debug(f"{repo_name} monitoring is disabled. Skipping.")
            return
        try:
            print("Calling fetch_commits") #! Debug print
            self.logger.debug("Calling fetch_commits")
            commits = await self.fetch_commits(api_key, repo_name)
            if commits:
                print(f"Found {len(commits)} commits for {repo_name}") #! Debug print
                self.logger.debug(f"Found {len(commits)} commits for {repo_name}")
                for commit in commits:
                    print(f"Posting commit for {repo_name}") #! Debug print
                    self.logger.info(f"Posting commit for {repo_name}")
                    await self.post_commit(int(guild_id), repo_name, commit)
        except Exception as e:
            print(f"Error checking {repo_name} in {guild_id}: {e}")

    # Using the GitHub API List Commits endpoint to fetch the commits for a repository.
    async def fetch_commits(self, api_key, repo_name):
        print(f"Fetching commits for {repo_name}") #! Debug print
        try: 
            url = f"https://api.github.com/repos/{repo_name}/commits"
            headers = {"Authorization": f"token {api_key}"}
            async with self.session.get(url, headers=headers) as resp:
                resp.raise_for_status()
                return await resp.json()
        except Exception as e:
            print(f"Error fetching commits for {repo_name}: {e}") #! Debug print
            self.logger.error(f"Error fetching commits for {repo_name}: {e}")
            return

    # Post commit notification to the  notification channel.
    async def post_commit(self, guild_id, repo_name, commit_data):
        guild = self.bot.get_guild(guild_id)
        print(f"Posting commit for {repo_name} to server {guild_id}") #! Debug print
        if not guild:
            print(f"No guild found for {guild_id}. Exiting.") #! Debug print
            return
        channel_id = self.data[str(guild_id)].get("notification_channel")
        channel = guild.get_channel(channel_id)
        print(f"Git notification channel: {channel_id}") #! Debug print
        if not channel:
            return
        try:
            print(f"Sending commit notification for {repo_name} in {channel}") #! Debug print
            self.logger.debug(f"Sending commit notification for {repo_name} in {channel}")
            embed = discord.Embed(title=f"New Commit Notification: {repo_name}",
                                  description=commit_data["commit"]["message"],
                                  color=discord.Color.purple())
            print(f"Embed created for commit.") #! Debug print
            self.logger.debug(f"Embed created for commit.")
            embed.set_author(name=commit_data["commit"]["author"]["name"],
                             icon_url=commit_data["author"]["avatar_url"])
            embed.add_field(name="Repository",
                            value=f"[{repo_name}](https://github.com/{repo_name})")
            embed.add_field(name="Author", value=commit_data["commit"]["author"]["name"], inline=True)
            embed.add_field(name="Date", value=commit_data["commit"]["author"]["date"], inline=True)
            print(f"Commit notification sent - Repo: {repo_name}, Channel: {channel}, Author: {commit_data["commit"]["author"]}, Repository: https://github.com/{repo_name}, Date: {commit_data["commit"]["author"]["date"]} ") #! Debug print
            self.logger.info(f"Commit notification sent - Repo: {repo_name}, Channel: {channel}, Author: {commit_data["commit"]["author"]}, Repository: https://github.com/{repo_name}, Date: {commit_data["commit"]["author"]["date"]} ")
            await channel.send(embed=embed)
            
        except Exception as e:
            print(f"Error sending commit notification for {repo_name} in {guild_id}: {e}")
            self.logger.error(f"Error sending commit notification for {repo_name} in {guild_id}: {e}")

    # Commands
    @commands.group()
    async def git(self, ctx):
        """GitHub integration commands."""
        
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @git.command()
    async def addrepo(self, ctx, repository: str):
        """Add a repo to the watchlist. Use the format {user}/{repo}"""
        guild_id = str(ctx.guild.id)
        if guild_id not in self.data:
            print(f"Creating new guild entry for {guild_id} in the configuration.") #! Debug print
            self.logger.info(f"Creating new guild entry for {guild_id} in the configuration.")
            self.data[guild_id] = {"watchlist": {}, "notification_channel": None}
        if repository in self.data[guild_id]["watchlist"]:
            print(f"{repository} is already in the watchlist.") #! Debug print
            self.logger.info(f"{repository} is already in the watchlist.")
            await ctx.send(f"{repository} is already in the watchlist.")
        else:
            print(f"Adding {repository} to the watchlist.") #! Debug print
            self.logger.info(f"Adding {repository} to the watchlist.")
            self.data[guild_id]["watchlist"][repository] = {"enabled": True}
            self.save_config()
            await ctx.send(f"Added {repository} to the watchlist.")

    @git.command()
    @commands.has_permissions(administrator=True)
    async def setchannel(self, ctx, channel: discord.TextChannel):
        """Set the notification channel for commit updates."""
        print(f"Setting notification channel to {channel.mention}") #! Debug print
        self.logger.debug(f"Setting notification channel to {channel.mention}")
        guild_id = str(ctx.guild.id)
        if guild_id not in self.data:
            print(f"Creating new guild entry for {guild_id} in the configuration.") #! Debug print
            self.logger.debug(f"Creating new guild entry for {guild_id} in the configuration.")
            self.data[guild_id] = {"watchlist": {}, "notification_channel": None}
        print(f"Setting notification channel to {channel.id}") #! Debug print
        self.logger.debug(f"Setting notification channel to {channel.id}")
        self.data[guild_id]["notification_channel"] = channel.id
        try: 
            self.save_config()
        except Exception as e:
            print(f"Error saving configuration: {e}")
            self.logger.error(f"Error saving configuration: {e}")
        await ctx.send(f"Notification channel set to {channel.mention}")

    @git.command()
    async def removerepo(self, ctx, repository: str):
        """Remove a repo from the watchlist. Use the format {user}/{repo}"""
        guild_id = str(ctx.guild.id)
        if guild_id in self.data and repository in self.data[guild_id]["watchlist"]:
            print(f"Removing {repository} from the watchlist.") #! Debug print
            self.logger.info(f"Removing {repository} from the watchlist.")
            del self.data[guild_id]["watchlist"][repository]
            self.save_config()
            await ctx.send(f"Removed {repository} from the watchlist.")
        else:
            print(f"{repository} is not in the watchlist.")
            self.logger.info(f"{repository} is not in the watchlist.")
            await ctx.send(f"{repository} is not in the watchlist.")

    @git.command()
    async def watchlist(self, ctx):
        """View the current GitHub watchlist."""
        guild_id = str(ctx.guild.id)
        if guild_id not in self.data or not self.data[guild_id]["watchlist"]:
            await ctx.send("The watchlist is empty.")
            return
        print(f"{guild_id} watchlist: {self.data[guild_id]["watchlist"]}") #! Debug print
        self.logger.debug(f"{guild_id} watchlist: {self.data[guild_id]["watchlist"]}")
        watchlist = self.data[guild_id]["watchlist"]
        embed = discord.Embed(title="GitHub Watchlist", color=discord.Color.purple())
        print(f"Embed created for watchlist.") #! Debug print
        for repo_name, repo_data in watchlist.items():
            status = "Enabled" if repo_data["enabled"] else "Disabled"
            embed.add_field(name=repo_name, value=status, inline=False)
        await ctx.send(embed=embed)


# Adding the cog to the bot
async def setup(bot):
    await bot.add_cog(GitMonitor(bot))
