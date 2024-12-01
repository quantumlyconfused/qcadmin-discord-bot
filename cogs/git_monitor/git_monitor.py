# GitMonitor: A cog for QCAdmin which interacts with the GitHub API to notify a Discord channel when a commit is made to one or more repositories. Commit notification is the first feature of the GitMonitor cog, with additional features to be added in the future.
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
from datetime import datetime 

class GitMonitor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = bot.logger
        load_dotenv()
        self.session = aiohttp.ClientSession()
        self.config = self.load_config()
        self.commit_check_loop.start()
        self.api_key = os.getenv('GITMONITOR_TOKEN')
        
        if not self.api_key:
            self.logger.error("Missing required GitMonitor dotenv variables")
            raise ValueError("Missing required GitMonitor dotenv variables")
        

    # Close the aiohttp session when the cog is unloaded. 
    def cog_unload(self):
        self.commit_check_loop.cancel()
        self.bot.loop.create_task(self.session.close())
        print("GitMonitor cog unloaded. HTTP session closed.") #! Debug print
        self.logger.info("GitMonitor cog unloaded. HTTP session closed.")
        

    # Load and save configuration
    def load_config(self):
        CONFIG_FILE = "./config/gitmonitor_config.json"
        try: 
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
            print(f'Configuration file loaded: {CONFIG_FILE}') #! Debug print
        # If the configuration file is not found or it is the first time loading the cog, create a new config with default settings
        except FileNotFoundError as e:
            print(f'Configuration file not found: {e}') #! Debug print
            self.logger.error(f"Configuration file not found: {e}")
            return {}
        default_config = {"watchlist": {}, "notification_channel": None}
        with open(CONFIG_FILE, "w") as f:
            json.dump(default_config, f, indent=4)
        return default_config


    def save_config(self):
        CONFIG_FILE = "./config/gitmonitor_config.json"
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
    @tasks.loop(minutes=30)
    async def commit_check_loop(self):
        print("Commit check task started.") #! Debug print
        self.logger.debug("Commit check task started.")
        for guild_id, guild_data in self.config.items():
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
            # Check if monitoring is enabled for the repository
            if not repo_data.get("enabled", True):  # Default to True if "enabled" is missing
                print(f"Monitoring is disabled for {repo_name}. Skipping.")  # Debug print
                self.logger.info(f"Monitoring is disabled for {repo_name}. Skipping.")
                continue
        for repo_name, repo_data in guild_data.get("watchlist", {}).items():
            print(f"Checking {repo_name} for commits") #! Debug print
            self.logger.debug(f"Checking {repo_name} for commits")
            await self.check_repo_commits(guild_id, self.api_key, repo_name, repo_data)

    async def check_repo_commits(self, guild_id, api_key, repo_name, repo_data):
        if not repo_data["enabled"]:
            print(f"{repo_name} monitoring is disabled. Skipping.")  #! Debug print
            return

        last_commit_sha = repo_data.get("last_commit_sha")
        print(f"Last seen SHA for {repo_name}: {last_commit_sha}")  # Debug print

        try:
            commits = await self.fetch_commits(api_key, repo_name, last_commit_sha)
            if not commits:
                print(f"No new commits for {repo_name}.")  # Debug print
                return

            # Process the latest commit (most recent first)
            for commit in reversed(commits):
                await self.post_commit(int(guild_id), repo_name, commit)

            # Update the last seen commit SHA
            latest_commit_sha = commits[0]["sha"]
            self.config[guild_id]["watchlist"][repo_name]["last_commit_sha"] = latest_commit_sha
            self.save_config()
        except Exception as e:
            print(f"Error checking {repo_name} in {guild_id}: {e}")

    # Using the GitHub API List Commits endpoint to fetch the commits for a repository.
    async def fetch_commits(self, api_key, repo_name, last_commit_sha=None):
        print(f"Fetching commits for {repo_name}") #! Debug print
        self.logger.debug(f"Fetching commits for {repo_name}")
        try: 
            url = f"https://api.github.com/repos/{repo_name}/commits"
            headers = {"Authorization": f"token {api_key}"}
            async with self.session.get(url, headers=headers) as resp:
                resp.raise_for_status()
                commits = await resp.json()

            # Filter for commits after last_commit_sha and put them in a list
            if last_commit_sha:
                    new_commits = []
                    for commit in commits:
                        if commit["sha"] == last_commit_sha:
                            break  
                        new_commits.append(commit)
                    print(f"Filtered {len(new_commits)} new commits for {repo_name}")  #! Debug print
                    self.logger.debug(f"Filtered {len(new_commits)} new commits for {repo_name}")
                    return new_commits

            # If no last_commit_sha, return all commits
            return commits
        
        except Exception as e:
            print(f"Error fetching commits for {repo_name}: {e}")  # Debug print
            self.logger.error(f"Error fetching commits for {repo_name}: {e}")
            return []
                
    # Post commit notification to the  notification channel.
    async def post_commit(self, guild_id, repo_name, commit_data):
        guild = self.bot.get_guild(guild_id)
        print(f"Posting commit for {repo_name} to server {guild_id}") #! Debug print
        if not guild:
            print(f"No guild found for {guild_id}. Exiting.") #! Debug print
            return
        channel_id = self.config[str(guild_id)].get("notification_channel")
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
            embed.add_field(name="Commit URL", value=commit_data["html_url"], inline=False)
            embed.add_field(name="Author", value=commit_data["commit"]["author"]["name"], inline=True)
            embed.add_field(name="Date", value=commit_data["commit"]["author"]["date"], inline=True)
            print(f"Commit notification sent - Repo: {repo_name}, Channel: {channel}, Author: {commit_data["commit"]["author"]}, Repository: https://github.com/{repo_name}, Date: {commit_data["commit"]["author"]["date"]} ") #! Debug print
            self.logger.info(f"Commit notification sent - Repo: {repo_name}, Channel: {channel}, Author: {commit_data["commit"]["author"]}, Repository: https://github.com/{repo_name}, Date: {commit_data["commit"]["author"]["date"]} ")
            await channel.send(embed=embed)
            
        except Exception as e:
            print(f"Error sending commit notification for {repo_name} in {guild_id}: {e}")
            self.logger.error(f"Error sending commit notification for {repo_name} in {guild_id}: {e}")

    @commands.group()
    async def gitmonitor(self, ctx):
        """Group of commands for GitHub monitoring."""
        if ctx.invoked_subcommand is None:
            await ctx.send("Invalid git command. Use `-gitmonitor help` to see available commands.")

    @gitmonitor.command()
    async def help(self, ctx):
        """Shows gitmonitor help message"""
        commands = {
            "addrepo {user}/{repo}": "Add a repo to the watchlist.",
            "setchannel {channel}": "Set the notification channel for commit updates.",
            "channel": "View the current git monitor notification channel.",
            "removerepo {user}/{repo}": "Remove a repo from the watchlist.",
            "repos": "View the current GitHub watchlist.",
            "checkrepos": "Manually check for commits in the watchlist."
        }
        embed = discord.Embed(title="GitMonitor Commands", color=discord.Color.purple())
        for command, description in commands.items():
            embed.add_field(name=command, value=description, inline=False)
        await ctx.send(embed=embed)
        
    @gitmonitor.command()
    @commands.has_permissions(manage_guild=True, manage_messages=True)
    async def setinterval(self, ctx, minutes: int):
        """Set the interval for the commit check loop in minutes."""
        if minutes < 1:
            await ctx.send("Interval must be at least 1 minute.")
            return
        self.commit_check_loop.change_interval(minutes=minutes)
        await ctx.send(f"Commit check interval set to {minutes} minutes.")
        print(f"Commit check interval set to {minutes} minutes.") #! Debug print
        self.logger.info(f"Commit check interval set to {minutes} minutes.")

    @gitmonitor.command()
    @commands.has_permissions(manage_guild=True, manage_messages=True)
    async def addrepo(self, ctx, repository: str):
        """Add a repo to the watchlist. Use the format {user}/{repo}"""
        guild_id = str(ctx.guild.id)
        if guild_id not in self.config:
            print(f"Creating new guild entry for {guild_id} in the configuration.") #! Debug print
            self.logger.info(f"Creating new guild entry for {guild_id} in the configuration.")
            self.config[guild_id]["watchlist"][repository] = {
                "enabled": True,
                "last_commit_sha": None
            }
        if repository in self.config[guild_id]["watchlist"]:
            print(f"{repository} is already in the watchlist.") #! Debug print
            self.logger.info(f"{repository} is already in the watchlist.")
            await ctx.send(f"{repository} is already in the watchlist.")
        else:
            print(f"Adding {repository} to the watchlist.") #! Debug print
            self.logger.info(f"Adding {repository} to the watchlist.")
            self.config[guild_id]["watchlist"][repository] = {
            "enabled": True,
            "last_commit_sha": None
            }
            self.save_config()
            await ctx.send(f"Added {repository} to the watchlist.")

    @gitmonitor.command()
    @commands.has_permissions(manage_guild=True, manage_messages=True)
    async def setchannel(self, ctx, channel: discord.TextChannel):
        """Set the notification channel for commit updates."""
        print(f"Setting notification channel to {channel.mention}") #! Debug print
        self.logger.debug(f"Setting notification channel to {channel.mention}")
        guild_id = str(ctx.guild.id)
        if guild_id not in self.config:
            print(f"Creating new guild entry for {guild_id} in the configuration.") #! Debug print
            self.logger.debug(f"Creating new guild entry for {guild_id} in the configuration.")
            self.config[guild_id] = {"watchlist": {}, "notification_channel": None}
        print(f"Setting notification channel to {channel.id}") #! Debug print
        self.logger.debug(f"Setting notification channel to {channel.id}")
        self.config[guild_id]["notification_channel"] = channel.id
        try: 
            self.save_config()
        except Exception as e:
            print(f"Error saving configuration: {e}")
            self.logger.error(f"Error saving configuration: {e}")
        await ctx.send(f"Notification channel set to {channel.mention}")
        
    @gitmonitor.command()
    @commands.has_permissions(manage_guild=True, manage_messages=True)
    async def channel(self, ctx):
        """View the current git monitor notification channel."""
        guild_id = str(ctx.guild.id)
        if guild_id not in self.config or not self.config[guild_id]["notification_channel"]:
            print(f"No notification channel found for {guild_id}.") #! Debug print
            self.logger.info(f"No notification channel found for {guild_id}.")
            await ctx.send("No notification channel set. Use **!setchannel {channel}** to set a channel.")
            return
        channel_id = self.config[guild_id]["notification_channel"]
        channel = ctx.guild.get_channel(channel_id)
        print(f"Notification channel: {channel.mention}") #! Debug print
        self.logger.debug(f"Notification channel: {channel.mention}")
        await ctx.send(f"Notification channel: {channel.mention}")
        

    @gitmonitor.command()
    @commands.has_permissions(manage_guild=True, manage_messages=True)
    async def removerepo(self, ctx, repository: str):
        """Remove a repo from the watchlist. Use the format {user}/{repo}"""
        guild_id = str(ctx.guild.id)
        if guild_id in self.config and repository in self.config[guild_id]["watchlist"]:
            print(f"Removing {repository} from the watchlist.") #! Debug print
            self.logger.info(f"Removing {repository} from the watchlist.")
            del self.config[guild_id]["watchlist"][repository]
            self.save_config()
            await ctx.send(f"Removed {repository} from the watchlist.")
        else:
            print(f"{repository} is not in the watchlist.")
            self.logger.info(f"{repository} is not in the watchlist.")
            await ctx.send(f"{repository} is not in the watchlist.")

    @gitmonitor.command()
    @commands.has_permissions(manage_guild=True, manage_messages=True)
    async def repos(self, ctx):
        """View the current GitHub watchlist."""
        guild_id = str(ctx.guild.id)
        if guild_id not in self.config or not self.config[guild_id]["watchlist"]:
            print(f"{guild_id} watchlist is empty.") #! Debug print
            await ctx.send("The watchlist is empty.")
            return
        print(f"{guild_id} watchlist: {self.config[guild_id]["watchlist"]}") #! Debug print
        self.logger.debug(f"{guild_id} watchlist: {self.config[guild_id]["watchlist"]}")
        watchlist = self.config[guild_id]["watchlist"]
        embed = discord.Embed(title="GitHub Watchlist", color=discord.Color.purple())
        print(f"Embed created for watchlist.") #! Debug print
        for repo_name, repo_data in watchlist.items():
            status = "Enabled" if repo_data["enabled"] else "Disabled"
            embed.add_field(name=repo_name, value=status, inline=False)
        await ctx.send(embed=embed)

    @gitmonitor.command()
    @commands.has_permissions(manage_guild=True, manage_messages=True)
    async def checkrepos (self, ctx):
        """Manually check for commits in the watchlist."""
        guild_id = str(ctx.guild.id)
        if guild_id not in self.config:
            print(f"No watchlist found for {guild_id}.")
            self.logger.info(f"No watchlist found for {guild_id}.")
            await ctx.send("No repos are being watched. Add a repo with **!addrepo {user}/{repo}**.")
            return
        await self.check_guild_repos(guild_id, self.config[guild_id])
        await ctx.send("Checking repos for new commits.")
        

# Adding the cog to the bot
async def setup(bot):
    await bot.add_cog(GitMonitor(bot))
    bot.logger.info("Cog loaded: GitMonitor v0.1")

