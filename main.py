import os
import re
import json
import asyncio
from typing import Optional, Dict, List, Tuple, Any
from datetime import datetime, timedelta

import discord
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput, Select
from discord.ext import commands, tasks

# =================== CONFIGURATION ===================
TOKEN = "MTQxNDAwOTk1ODI3MzUxNTY5MQ.GYDE5m.JtM9WyS7dQMAGZ4nblmTzaapc2wmezby3Bwz2I"
SETTINGS_FILE = "bot_settings.json"
LISTINGS_FILE = "active_listings.json"

# Default settings
DEFAULT_SETTINGS = {
    "embed_color": 0x5865F2,
    "minimal_emojis": False,
    "show_thumbnails": True,
    "show_separators": True,
    "auto_update_listings": True,
    "listing_channel": None,
    "mod_roles": [],
    "price_format": "USD",
    "show_detailed_stats": True
}
def parse_price(value: str) -> Optional[float]:
    """Extract numeric price from strings like '$50', '50 USD', '75'"""
    if not value:
        return None
    try:
        num = re.findall(r"[0-9]+(?:\\.[0-9]+)?", value.replace(",", ""))
        return float(num[0]) if num else None
    except Exception:
        return None


# =================== STAR COLORS & LEVELS ===================
BEDWARS_STARS = {
    0: ("✫", 0x7F7F7F, "Gray"),
    100: ("★", 0xFFFFFF, "White"),  
    200: ("⭐", 0xFFAA00, "Gold"),
    300: ("✦", 0x55FFFF, "Aqua"),
    400: ("✧", 0x00AA00, "Dark Green"),
    500: ("✩", 0x00AAAA, "Dark Aqua"),
    600: ("✪", 0xAA0000, "Dark Red"),
    700: ("✫", 0xFF55FF, "Light Purple"),
    800: ("✬", 0x5555FF, "Blue"),
    900: ("✭", 0xAA00AA, "Dark Purple"),
    1000: ("✮", 0xFFAA00, "Gold"),
    1100: ("✯", 0xFFFFFF, "White"),
    1200: ("✰", 0x55FFFF, "Aqua"),
    1300: ("✱", 0xFFAA00, "Gold"),
    1400: ("✲", 0x00AA00, "Green"),
    1500: ("✳", 0x00AAAA, "Dark Aqua"),
    1600: ("✴", 0xAA0000, "Dark Red"),
    1700: ("✵", 0xFF55FF, "Light Purple"),
    1800: ("✶", 0x5555FF, "Blue"),
    1900: ("✷", 0xAA00AA, "Dark Purple"),
    2000: ("✸", 0xFFD700, "Rainbow Start"),
}

SKYWARS_STARS = {
    0: ("☆", 0x7F7F7F, "Gray"),
    5: ("✙", 0xFFFFFF, "White"),
    10: ("✚", 0xFFAA00, "Gold"),
    15: ("✛", 0x55FFFF, "Aqua"),
    20: ("✜", 0x00AA00, "Green"),
    25: ("✝", 0x00AAAA, "Dark Aqua"),
    30: ("✞", 0xAA0000, "Dark Red"),
    35: ("✟", 0xFF55FF, "Light Purple"),
    40: ("✠", 0x5555FF, "Blue"),
    45: ("✡", 0xAA00AA, "Dark Purple"),
    50: ("☆", 0xFFD700, "Rainbow"),
}

DUELS_TITLES = [
    ("Rookie", 0x7F7F7F, "⚔"),
    ("Iron", 0xFFFFFF, "⚔"),
    ("Gold", 0xFFAA00, "⚔"),
    ("Diamond", 0x55FFFF, "⚔"),
    ("Master", 0x00AA00, "⚔"),
    ("Legend", 0xAA0000, "⚔"),
    ("Grandmaster", 0xFF55FF, "⚔"),
    ("Godlike", 0x5555FF, "⚔"),
    ("Celestial", 0xAA00AA, "⚔"),
    ("Divine", 0xFFD700, "⚔"),
]

# =================== DATA STORAGE ===================
class DataManager:
    def __init__(self):
        self.settings = self.load_settings()
        self.listings = self.load_listings()
    
    def load_settings(self) -> Dict:
        try:
            with open(SETTINGS_FILE, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
    
    def save_settings(self):
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(self.settings, f, indent=2)
    
    def load_listings(self) -> Dict:
        try:
            with open(LISTINGS_FILE, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
    
    def save_listings(self):
        with open(LISTINGS_FILE, 'w') as f:
            json.dump(self.listings, f, indent=2)
    
    def get_guild_settings(self, guild_id: int) -> Dict:
        return self.settings.get(str(guild_id), DEFAULT_SETTINGS.copy())
    
    def update_guild_settings(self, guild_id: int, new_settings: Dict):
        self.settings[str(guild_id)] = {**self.get_guild_settings(guild_id), **new_settings}
        self.save_settings()

data_manager = DataManager()

# =================== EMBED BUILDER ===================
class EmbedBuilder:
    @staticmethod
    def get_bedwars_star_display(level: int) -> Tuple[str, int, str]:
        for min_level in sorted(BEDWARS_STARS.keys(), reverse=True):
            if level >= min_level:
                return BEDWARS_STARS[min_level]
        return BEDWARS_STARS[0]
    
    @staticmethod
    def get_skywars_star_display(level: int) -> Tuple[str, int, str]:
        for min_level in sorted(SKYWARS_STARS.keys(), reverse=True):
            if level >= min_level:
                return SKYWARS_STARS[min_level]
        return SKYWARS_STARS[0]
    
    @staticmethod
    def format_number(num: int) -> str:
        if num >= 1000000:
            return f"{num/1000000:.1f}M"
        elif num >= 1000:
            return f"{num/1000:.1f}K"
        return str(num)
    
    @staticmethod
    def create_listing_embed(
        ign: str, seller: discord.User, stats: Dict[str, Any],
        bin_price: Optional[str], co: Optional[str], notes: Optional[str],
        guild_settings: Dict, custom_colors: Optional[Dict] = None
    ) -> discord.Embed:
        
        # Use custom embed color if provided, otherwise use guild settings
        if custom_colors and custom_colors.get("embed_color"):
            color = custom_colors["embed_color"]
        else:
            color = guild_settings.get("embed_color", DEFAULT_SETTINGS["embed_color"])
            
        minimal_emojis = guild_settings.get("minimal_emojis", False)
        show_thumbnails = guild_settings.get("show_thumbnails", True)
        show_separators = guild_settings.get("show_separators", True)
        show_detailed = guild_settings.get("show_detailed_stats", True)
        
        # Create embed
        embed = discord.Embed(
            title=f"{ign} — Account Listing",
            color=color,
            timestamp=datetime.utcnow()
        )
        
        # Author and thumbnail
        embed.set_author(
            name=f"Listed by {seller.display_name}",
            icon_url=seller.display_avatar.url if seller.display_avatar else None
        )
        
        if show_thumbnails:
            embed.set_thumbnail(url=f"https://mc-heads.net/avatar/{ign}/128")
        
        # Pricing section
        price_emoji = "💰" if not minimal_emojis else ""
        offer_emoji = "📈" if not minimal_emojis else ""
        
        embed.add_field(
            name=f"{price_emoji} Buy It Now",
            value=f"`{bin_price}`" if bin_price else "Not Set",
            inline=True
        )
        embed.add_field(
            name=f"{offer_emoji} Current Offer",
            value=f"`{co}`" if co else "None",
            inline=True
        )
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        
        if show_separators:
            embed.add_field(name="\u200b", value="─────────────────────", inline=False)
        
        # General stats
        general = stats.get("general", {})
        rank_display = f"[{general.get('rank', 'None')}]" if general.get('rank') else "None"
        level_display = str(general.get('network_level', 'Unknown'))
        
        general_info = f"**Rank:** `{rank_display}`\n**Network Level:** `{level_display}`"
        
        embed.add_field(
            name="📊 General Stats" if not minimal_emojis else "General Stats",
            value=general_info,
            inline=False
        )
        
        # BedWars stats
        bedwars = stats.get("bedwars", {})
        if bedwars.get("level", 0) > 0:
            star_icon, star_color, star_name = EmbedBuilder.get_bedwars_star_display(bedwars["level"])
            
            # Use custom color if provided
            if custom_colors and custom_colors.get("bedwars_color"):
                star_color = custom_colors["bedwars_color"]
            
            bedwars_text = f"{star_icon} **{bedwars['level']}★** ({star_name})"
            
            if show_detailed and bedwars.get("fkdr"):
                bedwars_text += f"\n`FKDR:` **{bedwars.get('fkdr', 0.0)}**"
            if show_detailed and bedwars.get("wins"):
                bedwars_text += f"\n`Wins:` **{EmbedBuilder.format_number(bedwars.get('wins', 0))}**"
            
            embed.add_field(
                name="🛏️ BedWars" if not minimal_emojis else "BedWars",
                value=bedwars_text,
                inline=True
            )
        
        # SkyWars stats
        skywars = stats.get("skywars", {})
        if skywars.get("level", 0) > 0:
            star_icon, star_color, star_name = EmbedBuilder.get_skywars_star_display(skywars["level"])
            
            # Use custom color if provided
            if custom_colors and custom_colors.get("skywars_color"):
                star_color = custom_colors["skywars_color"]
            
            skywars_text = f"{star_icon} **{skywars['level']}★** ({star_name})"
            
            if show_detailed and skywars.get("kdr"):
                skywars_text += f"\n`KDR:` **{skywars.get('kdr', 0.0)}**"
            if show_detailed and skywars.get("wins"):
                skywars_text += f"\n`Wins:` **{EmbedBuilder.format_number(skywars.get('wins', 0))}**"
            
            embed.add_field(
                name="⚔️ SkyWars" if not minimal_emojis else "SkyWars",
                value=skywars_text,
                inline=True
            )
        
        # Duels stats
        duels = stats.get("duels", {})
        if duels.get("title"):
            # Find title data
            title_data = next((t for t in DUELS_TITLES if t[0] == duels["title"]), DUELS_TITLES[0])
            title_name, title_color, title_icon = title_data
            
            # Use custom color if provided
            if custom_colors and custom_colors.get("duels_color"):
                title_color = custom_colors["duels_color"]
            
            duels_text = f"{title_icon} **{title_name}**"
            
            if show_detailed and duels.get("wins"):
                duels_text += f"\n`Wins:` **{EmbedBuilder.format_number(duels.get('wins', 0))}**"
            if show_detailed and duels.get("kdr"):
                duels_text += f"\n`KDR:` **{duels.get('kdr', 0.0)}**"
            
            embed.add_field(
                name="🗡️ Duels" if not minimal_emojis else "Duels",
                value=duels_text,
                inline=True
            )
        
        # Notes
        if notes:
            if show_separators:
                embed.add_field(name="\u200b", value="─────────────────────", inline=False)
            embed.add_field(
                name="📝 Additional Notes" if not minimal_emojis else "Notes",
                value=notes,
                inline=False
            )
        
        embed.set_footer(text="Created with Advanced Listing Bot")
        return embed

# =================== CUSTOM STAT SELECTION UI ===================
class StatSelectionView(View):
    def __init__(self, ign: str, seller: discord.User, bin_price: str = None, co: str = None, notes: str = None):
        super().__init__(timeout=300)
        self.ign = ign
        self.seller = seller
        self.bin_price = bin_price
        self.co = co
        self.notes = notes
        
        # Default stats
        self.stats = {
            "general": {"rank": "None", "network_level": 1},
            "bedwars": {"level": 0, "fkdr": 0.0, "wins": 0},
            "skywars": {"level": 0, "kdr": 0.0, "wins": 0},
            "duels": {"title": None, "wins": 0, "kdr": 0.0}
        }
        
        # Custom colors
        self.custom_colors = {
            "embed_color": 0x5865F2,
            "bedwars_color": None,
            "skywars_color": None,
            "duels_color": None
        }
    
    @discord.ui.button(label="Set General Stats", style=discord.ButtonStyle.primary, emoji="📊")
    async def set_general(self, interaction: discord.Interaction, button: Button):
        modal = GeneralStatsModal(self.stats["general"])
        modal.view = self
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Set BedWars", style=discord.ButtonStyle.primary, emoji="🛏️")
    async def set_bedwars(self, interaction: discord.Interaction, button: Button):
        modal = BedWarsStatsModal(self.stats["bedwars"])
        modal.view = self
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Set SkyWars", style=discord.ButtonStyle.primary, emoji="⚔️")
    async def set_skywars(self, interaction: discord.Interaction, button: Button):
        modal = SkyWarsStatsModal(self.stats["skywars"])
        modal.view = self
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Set Duels", style=discord.ButtonStyle.primary, emoji="🗡️")
    async def set_duels(self, interaction: discord.Interaction, button: Button):
        view = DuelsSelectionView(self.stats["duels"], self)
        embed = discord.Embed(title="Select Duels Title", color=0x5865F2)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="Customize Colors", style=discord.ButtonStyle.secondary, emoji="🎨")
    async def customize_colors(self, interaction: discord.Interaction, button: Button):
        modal = ColorCustomizationModal(self.custom_colors)
        modal.view = self
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Preview & Post", style=discord.ButtonStyle.success, emoji="👁️")
    async def preview_listing(self, interaction: discord.Interaction, button: Button):
        guild_settings = data_manager.get_guild_settings(interaction.guild_id)
        
        embed = EmbedBuilder.create_listing_embed(
            self.ign, self.seller, self.stats,
            self.bin_price, self.co, self.notes,
            guild_settings, self.custom_colors
        )
        
        view = ListingConfirmView(embed, interaction.channel_id, {
            "ign": self.ign,
            "seller_id": self.seller.id,
            "bin_price": self.bin_price,
            "co": self.co,
            "notes": self.notes,
            "stats": self.stats,
            "custom_colors": self.custom_colors,
            "created_at": datetime.utcnow().isoformat()
        })
        
        await interaction.response.send_message("Preview your listing:", embed=embed, view=view, ephemeral=True)

class GeneralStatsModal(Modal, title="Set General Stats"):
    rank = TextInput(label="Rank (e.g., MVP+, VIP)", placeholder="None", required=False, max_length=10)
    network_level = TextInput(label="Network Level", placeholder="1", max_length=4)
    
    def __init__(self, current_stats: Dict):
        super().__init__()
        self.rank.default = current_stats.get("rank", "None")
        self.network_level.default = str(current_stats.get("network_level", 1))
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            level = int(self.network_level.value) if self.network_level.value.isdigit() else 1
            self.view.stats["general"] = {
                "rank": self.rank.value or "None",
                "network_level": level
            }
            await interaction.response.send_message("✅ General stats updated!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Invalid network level!", ephemeral=True)

class BedWarsStatsModal(Modal, title="Set BedWars Stats"):
    level = TextInput(label="BedWars Star Level", placeholder="0", max_length=5)
    fkdr = TextInput(label="Final Kill/Death Ratio", placeholder="0.0", required=False, max_length=6)
    wins = TextInput(label="Wins", placeholder="0", required=False, max_length=8)
    
    def __init__(self, current_stats: Dict):
        super().__init__()
        self.level.default = str(current_stats.get("level", 0))
        self.fkdr.default = str(current_stats.get("fkdr", 0.0))
        self.wins.default = str(current_stats.get("wins", 0))
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            level = int(self.level.value) if self.level.value.isdigit() else 0
            fkdr = float(self.fkdr.value) if self.fkdr.value else 0.0
            wins = int(self.wins.value) if self.wins.value.isdigit() else 0
            
            self.view.stats["bedwars"] = {
                "level": level,
                "fkdr": fkdr,
                "wins": wins
            }
            await interaction.response.send_message("✅ BedWars stats updated!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Invalid stats format!", ephemeral=True)

class SkyWarsStatsModal(Modal, title="Set SkyWars Stats"):
    level = TextInput(label="SkyWars Star Level", placeholder="0", max_length=5)
    kdr = TextInput(label="Kill/Death Ratio", placeholder="0.0", required=False, max_length=6)
    wins = TextInput(label="Wins", placeholder="0", required=False, max_length=8)
    
    def __init__(self, current_stats: Dict):
        super().__init__()
        self.level.default = str(current_stats.get("level", 0))
        self.kdr.default = str(current_stats.get("kdr", 0.0))
        self.wins.default = str(current_stats.get("wins", 0))
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            level = int(self.level.value) if self.level.value.isdigit() else 0
            kdr = float(self.kdr.value) if self.kdr.value else 0.0
            wins = int(self.wins.value) if self.wins.value.isdigit() else 0
            
            self.view.stats["skywars"] = {
                "level": level,
                "kdr": kdr,
                "wins": wins
            }
            await interaction.response.send_message("✅ SkyWars stats updated!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Invalid stats format!", ephemeral=True)

class DuelsSelectionView(View):
    def __init__(self, current_stats: Dict, parent_view):
        super().__init__(timeout=300)
        self.current_stats = current_stats
        self.parent_view = parent_view
        
        # Add dropdown for title selection
        options = [
            discord.SelectOption(label=title[0], description=f"Color: {title[0]}", emoji=title[2])
            for title in DUELS_TITLES
        ]
        
        select = Select(placeholder="Choose Duels Title...", options=options)
        select.callback = self.title_selected
        self.add_item(select)
    
    async def title_selected(self, interaction: discord.Interaction):
        selected_title = interaction.data['values'][0]
        modal = DuelsStatsModal(self.current_stats, selected_title)
        modal.parent_view = self.parent_view
        await interaction.response.send_modal(modal)

class DuelsStatsModal(Modal, title="Set Duels Stats"):
    wins = TextInput(label="Wins", placeholder="0", max_length=8)
    kdr = TextInput(label="Kill/Death Ratio", placeholder="0.0", required=False, max_length=6)
    
    def __init__(self, current_stats: Dict, title: str):
        super().__init__()
        self.selected_title = title
        self.wins.default = str(current_stats.get("wins", 0))
        self.kdr.default = str(current_stats.get("kdr", 0.0))
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            wins = int(self.wins.value) if self.wins.value.isdigit() else 0
            kdr = float(self.kdr.value) if self.kdr.value else 0.0
            
            self.parent_view.stats["duels"] = {
                "title": self.selected_title,
                "wins": wins,
                "kdr": kdr
            }
            await interaction.response.send_message(f"✅ Duels stats updated! Title: {self.selected_title}", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Invalid stats format!", ephemeral=True)

class ColorCustomizationModal(Modal, title="Customize Colors"):
    embed_color = TextInput(label="Embed Color (hex)", placeholder="#5865F2", required=False, max_length=7)
    bedwars_color = TextInput(label="BedWars Color (hex)", placeholder="#FF5733", required=False, max_length=7)
    skywars_color = TextInput(label="SkyWars Color (hex)", placeholder="#33FF57", required=False, max_length=7)
    duels_color = TextInput(label="Duels Color (hex)", placeholder="#3357FF", required=False, max_length=7)
    
    def __init__(self, current_colors: Dict):
        super().__init__()
        if current_colors.get("embed_color"):
            self.embed_color.default = f"#{current_colors['embed_color']:06X}"
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            if self.embed_color.value:
                color_str = self.embed_color.value.lstrip('#')
                self.view.custom_colors["embed_color"] = int(color_str, 16)
            
            if self.bedwars_color.value:
                color_str = self.bedwars_color.value.lstrip('#')
                self.view.custom_colors["bedwars_color"] = int(color_str, 16)
            
            if self.skywars_color.value:
                color_str = self.skywars_color.value.lstrip('#')
                self.view.custom_colors["skywars_color"] = int(color_str, 16)
            
            if self.duels_color.value:
                color_str = self.duels_color.value.lstrip('#')
                self.view.custom_colors["duels_color"] = int(color_str, 16)
            
            await interaction.response.send_message("✅ Colors updated!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Invalid hex color format! Use #FF5733", ephemeral=True)

# =================== MAIN LISTING MODAL ===================
class ListingModal(Modal, title="Create Account Listing"):
    ign = TextInput(label="Minecraft Username", placeholder="Enter IGN...", max_length=16)
    bin_price = TextInput(label="Buy It Now Price", placeholder="e.g., $50 or 50 USD", required=False)
    co = TextInput(label="Current Offer", placeholder="e.g., $30 or 30 USD", required=False)
    notes = TextInput(
        label="Additional Notes",
        style=discord.TextStyle.paragraph,
        placeholder="Any additional information...",
        required=False,
        max_length=1000
    )
    
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        
        
    
    async def on_submit(self, interaction: discord.Interaction):
        # Show stat selection interface
        view = StatSelectionView(
            self.ign.value, 
            interaction.user, 
            self.bin_price.value or None,
            self.co.value or None, 
            self.notes.value or None
        )
        
        embed = discord.Embed(
            title=f"Customize Stats for {self.ign.value}",
            description="Set up your account stats using the buttons below. Click each section to customize it.",
            color=0x5865F2
        )
        
        embed.add_field(
            name="Instructions",
            value="• **General Stats**: Set rank and network level\n"
                  "• **BedWars/SkyWars**: Set star levels and ratios\n"
                  "• **Duels**: Choose title and set wins\n"
                  "• **Colors**: Customize embed and section colors\n"
                  "• **Preview**: View and post your listing",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# =================== REST OF THE COMPONENTS (UNCHANGED) ===================
class ListingConfirmView(View):
    def __init__(self, embed: discord.Embed, channel_id: int, listing_data: Dict):
        super().__init__(timeout=300)
        self.embed = embed
        self.channel_id = channel_id
        self.listing_data = listing_data
    
    @discord.ui.button(label="Post Listing", style=discord.ButtonStyle.success, emoji="📤")
    async def post_listing(self, interaction: discord.Interaction, button: Button):
        channel = interaction.client.get_channel(self.channel_id)
        if not channel:
            await interaction.response.send_message("Channel not found!", ephemeral=True)
            return
        
        message = await channel.send(embed=self.embed, view=ListingManageView(self.listing_data))
        
        listing_id = str(message.id)
        data_manager.listings[listing_id] = {
            **self.listing_data,
            "message_id": message.id,
            "channel_id": channel.id,
            "guild_id": interaction.guild_id
        }
        data_manager.save_listings()
        
        await interaction.response.send_message("✅ Listing posted successfully!", ephemeral=True)
        self.stop()
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_listing(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Listing cancelled.", ephemeral=True)
        self.stop()

class ListingManageView(View):
    def __init__(self, listing_data: Dict):
        super().__init__(timeout=None)
        self.listing_data = listing_data
    
    @discord.ui.button(label="Update Price", style=discord.ButtonStyle.primary, emoji="💰")
    async def update_price(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.listing_data["seller_id"]:
            await interaction.response.send_message("Only the seller can update this listing!", ephemeral=True)
            return
        
        modal = UpdatePriceModal(self.listing_data)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Get BIN", style=discord.ButtonStyle.success, emoji="💳")
    async def get_bin(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id == self.listing_data["seller_id"]:
            await interaction.response.send_message("You can't buy your own listing!", ephemeral=True)
            return
        
        if not self.listing_data.get("bin_price"):
            await interaction.response.send_message("No BIN price is set for this listing!", ephemeral=True)
            return
        
        view = BINConfirmView(self.listing_data, interaction.user)
        embed = discord.Embed(
            title="Confirm Purchase",
            description=f"Are you sure you want to buy **{self.listing_data['ign']}** for **{self.listing_data['bin_price']}**?",
            color=0x00FF00
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="Make Offer", style=discord.ButtonStyle.primary, emoji="📈")
    async def make_offer(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id == self.listing_data["seller_id"]:
            await interaction.response.send_message("You can't make an offer on your own listing!", ephemeral=True)
            return
        
        modal = MakeOfferModal(self.listing_data, interaction.user)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Mark as Sold", style=discord.ButtonStyle.success, emoji="✅")
    async def mark_sold(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.listing_data["seller_id"]:
            await interaction.response.send_message("Only the seller can mark this as sold!", ephemeral=True)
            return
        
        embed = interaction.message.embeds[0]
        embed.color = 0x00FF00
        embed.title = f"[SOLD] {embed.title}"
        
        await interaction.response.edit_message(embed=embed, view=None)
        
        if str(interaction.message.id) in data_manager.listings:
            del data_manager.listings[str(interaction.message.id)]
            data_manager.save_listings()

class BINConfirmView(View):
    def __init__(self, listing_data: Dict, buyer: discord.User):
        super().__init__(timeout=300)
        self.listing_data = listing_data
        self.buyer = buyer
    
    @discord.ui.button(label="Confirm Purchase", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm_purchase(self, interaction: discord.Interaction, button: Button):
        seller = interaction.guild.get_member(self.listing_data["seller_id"])
        if seller:
            try:
                embed = discord.Embed(
                    title="Account Sold!",
                    description=f"**{self.buyer.display_name}** has purchased **{self.listing_data['ign']}** for **{self.listing_data['bin_price']}**!",
                    color=0x00FF00
                )
                embed.add_field(name="Buyer", value=f"{self.buyer.mention}", inline=True)
                embed.add_field(name="Account", value=f"{self.listing_data['ign']}", inline=True)
                embed.add_field(name="Price", value=f"{self.listing_data['bin_price']}", inline=True)
                embed.add_field(name="Next Steps", value="Please coordinate the account transfer privately.", inline=False)
                
                await seller.send(embed=embed)
            except:
                pass
        
        await interaction.response.send_message(f"✅ Purchase confirmed! The seller has been notified. Please contact {seller.mention if seller else 'the seller'} to arrange the transfer.", ephemeral=True)
        self.stop()
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_purchase(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Purchase cancelled.", ephemeral=True)
        self.stop()

class MakeOfferModal(Modal, title="Make an Offer"):
    offer_amount = TextInput(label="Your Offer", placeholder="e.g., $45 or 45 USD", max_length=50)
    
    def __init__(self, listing_data: Dict, buyer: discord.User):
        super().__init__()
        self.listing_data = listing_data
        self.buyer = buyer
    
    async def on_submit(self, interaction: discord.Interaction):
        view = OfferConfirmView(self.listing_data, self.buyer, self.offer_amount.value)
        embed = discord.Embed(
            title="Confirm Offer",
            description=f"Are you sure you want to offer **{self.offer_amount.value}** for **{self.listing_data['ign']}**?",
            color=0x5865F2
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class OfferConfirmView(View):
    def __init__(self, listing_data: Dict, buyer: discord.User, offer_amount: str):
        super().__init__(timeout=300)
        self.listing_data = listing_data
        self.buyer = buyer
        self.offer_amount = offer_amount
    
    @discord.ui.button(label="Send Offer", style=discord.ButtonStyle.success, emoji="📤")
    async def send_offer(self, interaction: discord.Interaction, button: Button):
        seller = interaction.guild.get_member(self.listing_data["seller_id"])
        if seller:
            try:
                embed = discord.Embed(
                    title="New Offer Received!",
                    description=f"**{self.buyer.display_name}** has made an offer on **{self.listing_data['ign']}**!",
                    color=0x5865F2
                )
                embed.add_field(name="Offer Amount", value=f"{self.offer_amount}", inline=True)
                embed.add_field(name="Current BIN", value=f"{self.listing_data.get('bin_price', 'Not Set')}", inline=True)
                embed.add_field(name="Buyer", value=f"{self.buyer.mention}", inline=True)
                embed.add_field(name="Accept Offer?", value="You can accept this offer or wait for a higher one. Contact the buyer directly to negotiate.", inline=False)
                
                await seller.send(embed=embed)
            except:
                pass
        
        await interaction.response.send_message(f"✅ Offer sent! The seller has been notified of your **{self.offer_amount}** offer.", ephemeral=True)
        self.stop()
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_offer(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Offer cancelled.", ephemeral=True)
        self.stop()

class UpdatePriceModal(Modal, title="Update Listing Prices"):
    bin_price = TextInput(label="New BIN Price", placeholder="e.g., $60 or 60 USD", required=False)
    co = TextInput(label="New Current Offer", placeholder="e.g., $45 or 45 USD", required=False)
    
    def __init__(self, listing_data: Dict):
        super().__init__()
        self.listing_data = listing_data
    
    async def on_submit(self, interaction: discord.Interaction):
        if self.bin_price.value:
            self.listing_data["bin_price"] = self.bin_price.value
        if self.co.value:
            self.listing_data["co"] = self.co.value
        
        message_id = str(interaction.message.id)
        if message_id in data_manager.listings:
            data_manager.listings[message_id].update(self.listing_data)
            data_manager.save_listings()
        
        guild_settings = data_manager.get_guild_settings(interaction.guild_id)
        stats = self.listing_data.get("stats", {})
        custom_colors = self.listing_data.get("custom_colors", {})
        
        embed = EmbedBuilder.create_listing_embed(
            self.listing_data["ign"],
            interaction.user,
            stats,
            self.listing_data.get("bin_price"),
            self.listing_data.get("co"),
            self.listing_data.get("notes"),
            guild_settings,
            custom_colors
        )
        
        await interaction.response.edit_message(embed=embed)

class SettingsView(View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id
    
    @discord.ui.button(label="Embed Color", style=discord.ButtonStyle.secondary, emoji="🎨")
    async def change_color(self, interaction: discord.Interaction, button: Button):
        modal = ColorModal(self.guild_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Toggle Minimal Emojis", style=discord.ButtonStyle.secondary, emoji="😊")
    async def toggle_emojis(self, interaction: discord.Interaction, button: Button):
        settings = data_manager.get_guild_settings(self.guild_id)
        settings["minimal_emojis"] = not settings.get("minimal_emojis", False)
        data_manager.update_guild_settings(self.guild_id, settings)
        
        status = "enabled" if settings["minimal_emojis"] else "disabled"
        await interaction.response.send_message(f"Minimal emojis {status}!", ephemeral=True)
    
    @discord.ui.button(label="Toggle Thumbnails", style=discord.ButtonStyle.secondary, emoji="🖼️")
    async def toggle_thumbnails(self, interaction: discord.Interaction, button: Button):
        settings = data_manager.get_guild_settings(self.guild_id)
        settings["show_thumbnails"] = not settings.get("show_thumbnails", True)
        data_manager.update_guild_settings(self.guild_id, settings)
        
        status = "enabled" if settings["show_thumbnails"] else "disabled"
        await interaction.response.send_message(f"Thumbnails {status}!", ephemeral=True)
    
    @discord.ui.button(label="Toggle Detailed Stats", style=discord.ButtonStyle.secondary, emoji="📊")
    async def toggle_detailed(self, interaction: discord.Interaction, button: Button):
        settings = data_manager.get_guild_settings(self.guild_id)
        settings["show_detailed_stats"] = not settings.get("show_detailed_stats", True)
        data_manager.update_guild_settings(self.guild_id, settings)
        
        status = "enabled" if settings["show_detailed_stats"] else "disabled"
        await interaction.response.send_message(f"Detailed stats {status}!", ephemeral=True)

class ColorModal(Modal, title="Change Embed Color"):
    color = TextInput(
        label="Hex Color Code",
        placeholder="e.g., #FF5733 or FF5733",
        min_length=6,
        max_length=7
    )
    
    def __init__(self, guild_id: int):
        super().__init__()
        self.guild_id = guild_id
    
    async def on_submit(self, interaction: discord.Interaction):
        color_str = self.color.value.lstrip('#')
        try:
            color_int = int(color_str, 16)
            settings = {"embed_color": color_int}
            data_manager.update_guild_settings(self.guild_id, settings)
            await interaction.response.send_message(f"✅ Embed color updated to #{color_str.upper()}!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Invalid hex color! Use format: #FF5733", ephemeral=True)

# =================== DISCORD BOT ===================
class AdvancedListingBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)
    
    async def setup_hook(self):
        await self.tree.sync()
        print(f"Synced {len(self.tree.get_commands())} commands")

bot = AdvancedListingBot()

# =================== SLASH COMMANDS ===================
@bot.tree.command(name="list", description="Create a new account listing with custom stats")
async def create_listing(interaction: discord.Interaction):
    """Create a new account listing with manual stat customization"""
    modal = ListingModal(bot)
    await interaction.response.send_modal(modal)

@bot.tree.command(name="settings", description="Configure bot settings for this server")
@app_commands.default_permissions(manage_guild=True)
async def server_settings(interaction: discord.Interaction):
    """Configure bot settings for the server"""
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("You need Manage Server permissions to use this command.", ephemeral=True)
        return
    
    settings = data_manager.get_guild_settings(interaction.guild_id)
    
    embed = discord.Embed(
        title="Server Settings",
        color=settings.get("embed_color", DEFAULT_SETTINGS["embed_color"]),
        description="Configure how the listing bot behaves in this server."
    )
    
    embed.add_field(
        name="Current Settings",
        value=f"**Embed Color:** #{settings.get('embed_color', DEFAULT_SETTINGS['embed_color']):06X}\n"
              f"**Minimal Emojis:** {'Yes' if settings.get('minimal_emojis') else 'No'}\n"
              f"**Show Thumbnails:** {'Yes' if settings.get('show_thumbnails', True) else 'No'}\n"
              f"**Detailed Stats:** {'Yes' if settings.get('show_detailed_stats', True) else 'No'}\n"
              f"**Show Separators:** {'Yes' if settings.get('show_separators', True) else 'No'}",
        inline=False
    )
    
    view = SettingsView(interaction.guild_id)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

@bot.tree.command(name="mylistings", description="View and manage your active listings")
async def my_listings(interaction: discord.Interaction):
    """View user's active listings"""
    user_listings = []
    for listing_id, listing in data_manager.listings.items():
        if listing.get("seller_id") == interaction.user.id:
            user_listings.append((listing_id, listing))
    
    if not user_listings:
        await interaction.response.send_message("You don't have any active listings.", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="Your Active Listings",
        color=0x5865F2,
        description=f"You have {len(user_listings)} active listing(s)"
    )
    
    for listing_id, listing in user_listings[:10]:
        value = ""
        if listing.get("bin_price"):
            value += f"**BIN:** {listing['bin_price']}\n"
        if listing.get("co"):
            value += f"**C/O:** {listing['co']}\n"
        
        general = listing.get("stats", {}).get("general", {})
        if general.get("rank"):
            value += f"**Rank:** [{general['rank']}]"
        
        embed.add_field(
            name=listing.get("ign", "Unknown"),
            value=value or "No pricing set",
            inline=True
        )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="cleanlistings", description="Remove inactive/old listings (Admin)")
@app_commands.default_permissions(administrator=True)
async def clean_listings(interaction: discord.Interaction):
    """Clean up old or invalid listings"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Admin permissions required.", ephemeral=True)
        return
    
    removed_count = 0
    to_remove = []
    
    for listing_id, listing in data_manager.listings.items():
        try:
            channel = bot.get_channel(listing.get("channel_id"))
            if not channel:
                to_remove.append(listing_id)
                continue
            
            message = await channel.fetch_message(listing.get("message_id"))
            if not message:
                to_remove.append(listing_id)
        except:
            to_remove.append(listing_id)
    
    for listing_id in to_remove:
        del data_manager.listings[listing_id]
        removed_count += 1
    
    if removed_count > 0:
        data_manager.save_listings()
    
    await interaction.response.send_message(f"Cleaned up {removed_count} inactive listings.", ephemeral=True)

@bot.tree.command(name="liststats", description="Show bot usage statistics (Admin)")
@app_commands.default_permissions(administrator=True)
async def list_stats(interaction: discord.Interaction):
    """Show bot statistics"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Admin permissions required.", ephemeral=True)
        return
    
    total_listings = len(data_manager.listings)
    guild_listings = len([l for l in data_manager.listings.values() if l.get("guild_id") == interaction.guild_id])
    
    embed = discord.Embed(title="Bot Statistics", color=0x5865F2)
    embed.add_field(name="Total Active Listings", value=str(total_listings), inline=True)
    embed.add_field(name="This Server", value=str(guild_listings), inline=True)
    embed.add_field(name="Servers", value=str(len(bot.guilds)), inline=True)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# =================== ERROR HANDLING ===================
@bot.event
async def on_error(event, *args, **kwargs):
    print(f"Error in {event}: {args}")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    print(f"Command error: {error}")

@bot.event
async def on_ready():
    print(f"🚀 {bot.user} is online!")
    print(f"📊 Connected to {len(bot.guilds)} servers")
    print(f"📝 {len(data_manager.listings)} active listings loaded")
    
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{len(data_manager.listings)} listings | /list to start"
        )
    )

# =================== BOT STARTUP ===================
if __name__ == "__main__":
    if not TOKEN or "YOUR_BOT_TOKEN" in TOKEN:
        print("❌ Please set a valid Discord bot token!")
        print("   Get one from: https://discord.com/developers/applications")
    else:
        print("🔥 Starting Advanced Listing Bot...")
        try:
            bot.run(TOKEN)
        except Exception as e:
            print(f"❌ Failed to start bot: {e}")
            print("   Check your token and internet connection.")