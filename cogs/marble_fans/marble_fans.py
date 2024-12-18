#Marble Fans: A cog for QCAdmin which interacts with the Youtube API to monitor Jelle's Marble League channel for new videos. Will also scrape the Jelle's Marble Runs wiki for results and allow server members to pick their team.
#
# Author:
#    Dave Chadwick (github.com/ropeadope62)
# Version:
#    0.1

import discord
from discord import app_commands
from discord.ext import commands, tasks
import aiohttp
import os
from dotenv import load_dotenv
import time
from bs4 import BeautifulSoup
import googleapiclient.discovery

class MarbleFans(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = bot.logger # pass our existing QCAdmin logger to the cog
        load_dotenv()
        #! As with other QCAdmin containerized cogs, we will pass the env variables directly to the docker run
        self.youtube_api_key = os.getenv("YOUTUBE_API_KEY")
        self.channel_id = 'UCYJdpnjuSWVOLgGT9fIzL0g' # Jelle's Marble Runs channel
        self.wiki_url = "https://jellesmarbleruns.fandom.com/wiki/Marble_League_2024"
        
        if not all([self.youtube_api_key, self.channel_id]):
            self.logger.error("Youtube API key needs to be set.")
            raise ValueError("Youtube API key needs to be set.")
        
        self.youtube = googleapiclient.discovery.build(
            'youtube', 'v3', developerKey=self.youtube_api_key
        )
        
        # Start the background task for checking new videos
        self.check_new_videos.start()

    def cog_unload(self):
        # Make sure the event check loop is terminated when the cog is unloaded
        self.check_new_videos.cancel()

    @tasks.loop(minutes=30)
    async def check_new_videos(self):
        """Check for new videos from Jelle's Marble Runs channel"""
        if self.channel_id is None:
            self.logger.error("Channel ID is not set")
            #! Below is boilerplate and will require testing
        try:
            request = self.youtube.search().list(
                part="snippet",
                channelId=self.channel_id,
                order="date",
                maxResults=1
            )
            response = request.execute()

            if response["items"]:
                latest_video = response["items"][0]
                # TODO: Compare with last known video and notify if new
                self.logger.info(f"Checked for new videos: {latest_video['snippet']['title']}")

        except Exception as e:
            self.logger.error(f"Error checking for new videos: {str(e)}")

    @commands.group(name="marble", description="Marble Fans Cog - About")
    async def marble_group(self, Interaction: discord.Interaction):
        """Group for Marble League commands"""
        # TODO: Build an about embed for the cog which will display if no subcommands are invoked
        pass


    @marble_group.command(name="pick_team", description="Choose your favorite team")
    async def pick_team(self, Interaction: discord.Interaction, team_name: str):
        """Allows a user to pick their favorite team"""
        await Interaction.response.defer()
        
        # TODO: Determine some method to track a complete list of league teams. Keep discord member ID to team mapping in json. 
        # TODO: Team info can be scraped from https://jellesmarbleruns.fandom.com/wiki/Marble_League_Teams#List_of_Teams_and_Their_Uniform_Colors
        
        await Interaction.followup.send(f"🔵 Team selection: {team_name} (Feature coming soon!)")

    @marble_group.command(name="standings", description="View current Marble League standings")
    async def standings(self, Interaction: discord.Interaction):
        """Fetches and displays current Marble League standings"""
        await Interaction.response.defer()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.wiki_url) as response:
                    if response.status == 200:
                        # TODO: Scrape Marble League fan wiki results/standings to populate discord embeds
                        await Interaction.followup.send("📊 Standings feature coming soon!")
                    else:
                        await Interaction.followup.send("❌ Failed to fetch standings")
        except Exception as e:
            self.logger.error(f"Error fetching standings: {str(e)}")
            await Interaction.followup.send(f"❌ Error occurred: {str(e)}")
            
    @marble_group.command(name="records", description="View the current Marble League records")
    async def records(self, Interaction: discord.Interaction):
        """Fetches and displays current Marble League records"""
        await Interaction.response.defer()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.wiki_url) as response:
                    if response.status == 200:
                        #TODO: using bs4 extract the html for the records table https://jellesmarbleruns.fandom.com/wiki/List_of_Marble_League_Records
                        #TODO: if data needs to be cleaned up, use pandas dataframe before formatting into discord embed
        except Exception as e:
            self.logger.error(f"Error fetching records: {str(e)}")
            await Interaction.followup.send(f"❌ Error occurred: {str(e)}")

    @marble_group.command(name="performance", description="Get data on a specific Marble's historical performance")
    async def performance(self, Interaction: discord.Interaction, marble_name: str, event: str):
        """Fetches and displays historical performance data for a specific marble"""
        await Interaction.response.defer()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.wiki_url) as response:
                    if response.status == 200:
                        #TODO: extract table https://jellesmarbleruns.fandom.com/wiki/List_of_Individual_Performances_in_the_Marble_League
                        #TODO: One of two parameters will be required, event or marble_name, format the filtered data into an embed

    @marble_group.command(name="latest", description="Get the latest Marble League video")
    async def latest(self, Interaction: discord.Interaction):
        """Fetches and displays the latest video from the channel"""
        await Interaction.response.defer()

        try:
            request = self.youtube.search().list(
                part="snippet",
                channelId=self.channel_id,
                order="date",
                maxResults=1
            )
            response = request.execute()

            if response["items"]:
                video = response["items"][0]
                video_id = video["id"]["videoId"]
                title = video["snippet"]["title"]
                url = f"https://www.youtube.com/watch?v={video_id}"
    
                embed = discord.Embed(
                    title="Latest Marble League Video",
                    description=title,
                    url=url,
                    color=discord.Color.red()
                )
                embed.set_thumbnail(url=video["snippet"]["thumbnails"]["high"]["url"])
    
                await Interaction.followup.send(embed=embed)
            else:
                await Interaction.followup.send("❌ No videos found")
    
        except Exception as e:
            self.logger.error(f"Error fetching latest video: {str(e)}")
            await Interaction.followup.send(f"❌ Error occurred: {str(e)}")

    @app_commands.command(name="marble_commands", description="List all Marble Fans Cog commands")
    async def list_commands(self, Interaction: discord.Interaction):
        """Lists all available Marble Fans Cog commands"""
        commands_list = [
            "/marble commands - List all Marble League Cog commands",
            "/marble pick_team <team_name> - Choose your favorite Marble League team",
            "/marble team_info <team_name> - Get information about a specific Marble League team",
            "/marble standings - View current Marble League standings",
            "/marble latest - Get the latest Marble League Event Video"
        ]

        embed = discord.Embed(
            title="Marble Fans - Commands",
            description="List of all available commands",
            color=discord.Color.blue()
        )

        for command in commands_list:
            name, description = command.split(" - ")
            embed.add_field(name=name, value=description, inline=False)

        await Interaction.response.send_message(embed=embed)

    @app_commands.command(name="pick_team", description="Choose your favorite marble team")
    async def pick_team(self, Interaction: discord.Interaction, team_name: str):
        """Allows a user to pick their favorite marble team"""
        await Interaction.response.defer()
        
        # TODO: Implement team selection logic and database storage
        await Interaction.followup.send(f"🔵 Team selection: {team_name} (Feature coming soon!)")

    @app_commands.command(name="standings", description="View current Marble League standings")
    async def standings(self, Interaction: discord.Interaction):
        """Fetches and displays current Marble League standings"""
        await Interaction.response.defer()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.wiki_url) as response:
                    if response.status == 200:
                        # TODO: Implement wiki scraping logic
                        await Interaction.followup.send("📊 Standings feature coming soon!")
                    else:
                        await Interaction.followup.send("❌ Failed to fetch standings")
        except Exception as e:
            self.logger.error(f"Error fetching standings: {str(e)}")
            await Interaction.followup.send(f"❌ Error occurred: {str(e)}")

    @app_commands.command(name="latest_video", description="Get the latest Jelle's Marble Runs video")
    async def latest_video(self, Interaction: discord.Interaction):
        """Fetches and displays the latest video from the channel"""
        await Interaction.response.defer()

        try:
            request = self.youtube.search().list(
                part="snippet",
                channelId=self.channel_id,
                order="date",
                maxResults=1
            )
            response = request.execute()

            if response["items"]:
                video = response["items"][0]
                video_id = video["id"]["videoId"]
                title = video["snippet"]["title"]
                url = f"https://www.youtube.com/watch?v={video_id}"

                embed = discord.Embed(
                    title="Latest Marble League Video",
                    description=title,
                    url=url,
                    color=discord.Color.red()
                )
                embed.set_thumbnail(url=video["snippet"]["thumbnails"]["high"]["url"])

                await Interaction.followup.send(embed=embed)
            else:
                await Interaction.followup.send("❌ No videos found")

        except Exception as e:
            self.logger.error(f"Error fetching latest video: {str(e)}")
            await Interaction.followup.send(f"❌ Error occurred: {str(e)}")

async def setup(bot):
    await bot.add_cog(MarbleFans(bot))
    bot.logger.info("Cog loaded: MarbleLeague v0.1")

