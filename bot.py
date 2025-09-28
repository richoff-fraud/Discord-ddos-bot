import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import asyncio
import aiohttp
import json
import secrets
import string
from datetime import datetime, timedelta
import os

# Bot configuration
TOKEN = "" # Put in your discord token
SUPER_ADMIN_ID = 1234  # Change this to your discord id
STATUS_CHANNEL_ID = 1234  # Change to your status channel

# Database version for migrations
DATABASE_VERSION = 3

def get_database_version():
    """Get current database version"""
    try:
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute("SELECT version FROM database_info ORDER BY id DESC LIMIT 1")
        result = c.fetchone()
        conn.close()
        return result[0] if result else 0
    except sqlite3.OperationalError:
        return 0

def set_database_version(version):
    """Set database version"""
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    try:
        c.execute('''CREATE TABLE IF NOT EXISTS database_info
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      version INTEGER,
                      updated_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
        c.execute("INSERT INTO database_info (version) VALUES (?)", (version,))
        conn.commit()
        print(f"? Database updated to version {version}")
    except Exception as e:
        print(f"? Error during database version update: {e}")
    finally:
        conn.close()

def migrate_database():
    """Migrate database to latest version while preserving data"""
    current_version = get_database_version()
    print(f"?? Current database version: {current_version}")
    print(f"?? Target database version: {DATABASE_VERSION}")
    
    if current_version >= DATABASE_VERSION:
        print("? Database is already updated!")
        return
    
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    
    try:
        # Migration from version 0 to 1 (initial setup)
        if current_version < 1:
            print("?? Migrerer to version 1...")
            
            # Create basic tables if they don't exist
            c.execute('''CREATE TABLE IF NOT EXISTS users
                         (user_id INTEGER PRIMARY KEY, 
                          key_used TEXT,
                          vip INTEGER DEFAULT 0,
                          max_time INTEGER DEFAULT 60,
                          concurrent_attacks INTEGER DEFAULT 1,
                          expires_at TEXT,
                          created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
            
            c.execute('''CREATE TABLE IF NOT EXISTS keys
                         (key_id TEXT PRIMARY KEY,
                          created_by INTEGER,
                          max_time INTEGER DEFAULT 60,
                          concurrent_attacks INTEGER DEFAULT 1,
                          vip INTEGER DEFAULT 0,
                          expires_at TEXT,
                          used_by INTEGER DEFAULT NULL,
                          created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
            
            c.execute('''CREATE TABLE IF NOT EXISTS staff
                         (user_id INTEGER PRIMARY KEY,
                          added_by INTEGER,
                          created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
            
            c.execute('''CREATE TABLE IF NOT EXISTS admins
                         (user_id INTEGER PRIMARY KEY,
                          added_by INTEGER,
                          created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
            
            print("? Basic tables created")
        
        # Migration from version 1 to 2 (add status table)
        if current_version < 2:
            print("?? Migrating to version 2 - Adding status system...")
            
            c.execute('''CREATE TABLE IF NOT EXISTS status
                         (id INTEGER PRIMARY KEY,
                          status TEXT,
                          message TEXT,
                          eta TEXT,
                          updated_by INTEGER,
                          updated_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
            
            print("? Status table Added")
        
        # Migration from version 2 to 3 (add any future features)
        if current_version < 3:
            print("?? Migrating to version 3 - Adding new features...")
            
            # Check and add missing columns to existing tables
            try:
                # Check if concurrent_attacks column exists in users table
                c.execute("PRAGMA table_info(users)")
                columns = [column[1] for column in c.fetchall()]
                
                if 'concurrent_attacks' not in columns:
                    c.execute("ALTER TABLE users ADD COLUMN concurrent_attacks INTEGER DEFAULT 1")
                    print("? Added concurrent_attacks column to users")
                
                if 'vip' not in columns:
                    c.execute("ALTER TABLE users ADD COLUMN vip INTEGER DEFAULT 0")
                    print("? Added VIP column for users")
                
                if 'max_time' not in columns:
                    c.execute("ALTER TABLE users ADD COLUMN max_time INTEGER DEFAULT 60")
                    print("? Added max_time column to users")
                
            except Exception as e:
                print(f"?? Column migration error (can be ignored if columns already exist)): {e}")
            
            # Check keys table
            try:
                c.execute("PRAGMA table_info(keys)")
                key_columns = [column[1] for column in c.fetchall()]
                
                if 'concurrent_attacks' not in key_columns:
                    c.execute("ALTER TABLE keys ADD COLUMN concurrent_attacks INTEGER DEFAULT 1")
                    print("? Tilføjet concurrent_attacks kolonne til keys")
                
                if 'vip' not in key_columns:
                    c.execute("ALTER TABLE keys ADD COLUMN vip INTEGER DEFAULT 0")
                    print("? Added vip column to keys")
                
            except Exception as e:
                print(f"?? Keys tabel migration error: {e}")
            
            print("? Version 3 migration done")
        
        # Commit all changes
        conn.commit()
        
        # Update database version
        set_database_version(DATABASE_VERSION)
        
        print(f"?? Database migration complete! Version {current_version} ? {DATABASE_VERSION}")
        
    except Exception as e:
        print(f"? Database migration error: {e}")
        conn.rollback()
    finally:
        conn.close()

def init_db():
    """Initialize database with migration support"""
    print("?? Initialiserer database...")
    
    # Check if database file exists
    db_exists = os.path.exists('bot_data.db')
    
    if db_exists:
        print("?? Existing database found - preserving data")
    else:
        print("?? New database is created")
    
    # Run migrations
    migrate_database()
    
    # Verify all tables exist
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    
    # Get all table names
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [table[0] for table in c.fetchall()]
    
    expected_tables = ['users', 'keys', 'staff', 'admins', 'status', 'database_info']
    missing_tables = [table for table in expected_tables if table not in tables]
    
    if missing_tables:
        print(f"?? Missing tables: {missing_tables}")
    else:
        print("? All tables verified")
    
    # Show database statistics
    try:
        c.execute("SELECT COUNT(*) FROM users")
        user_count = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM keys")
        key_count = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM staff")
        staff_count = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM admins")
        admin_count = c.fetchone()[0]
        
        print(f"?? Database statistik:")
        print(f"   ?? Brugere: {user_count}")
        print(f"   ?? Keys: {key_count}")
        print(f"   ??? Staff: {staff_count}")
        print(f"   ?? Admins: {admin_count}")
        
    except Exception as e:
        print(f"?? Failed to retrieve statistics: {e}")
    
    conn.close()
    print("? Database initialization complete!")

# Attack methods configuration
ATTACK_METHODS = {
    "method 1": {
        "api": "Your api",
        "vip": False
    },    ,
    "Method 2": {
        "api": "Your api",
        "vip": True
    }
}

class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)

    async def setup_hook(self):
        try:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} slash commands")
        except Exception as e:
            print(f"Failed to sync commands: {e}")

bot = Bot()

def generate_key():
    return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))

def is_super_admin(user_id):
    """Only hardcoded admin (you) Can remove/add admins"""
    return user_id == SUPER_ADMIN_ID

def is_admin(user_id):
    """Check if user is admin (super admin or regular admin)"""
    if is_super_admin(user_id):
        return True
    
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    try:
        c.execute("SELECT user_id FROM admins WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        return result is not None
    except sqlite3.OperationalError:
        return False
    finally:
        conn.close()

def is_staff(user_id):
    if is_admin(user_id):
        return True
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    try:
        c.execute("SELECT user_id FROM staff WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        return result is not None
    except sqlite3.OperationalError:
        return False
    finally:
        conn.close()

def get_user_permissions(user_id):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    try:
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        return result
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()

# Function to update channel name based on status
async def update_status_channel_name(status):
    try:
        channel = bot.get_channel(STATUS_CHANNEL_ID)
        if channel:
            if status == "online":
                new_name = "??status-online"
            elif status == "testing":
                new_name = "??status-testing"
            else:  # offline
                new_name = "??status-offline"
            
            # Only update if name is different to avoid rate limits
            if channel.name != new_name:
                await channel.edit(name=new_name)
                print(f"Updated channel name to: {new_name}")
    except Exception as e:
        print(f"Error updating channel name: {e}")

# Status Selection View
class StatusSelectionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label='🟢 Online', style=discord.ButtonStyle.green)
    async def online_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_status(interaction, "online", "🟢", 0x00ff00)

    @discord.ui.button(label='🟡 Testing', style=discord.ButtonStyle.secondary)
    async def testing_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = StatusModal("testing", "🟡", 0xffff00)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='🔴 Offline', style=discord.ButtonStyle.danger)
    async def offline_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = StatusModal("offline", "🔴", 0xff0000)
        await interaction.response.send_modal(modal)

    async def update_status(self, interaction, status, emoji, color):
        # Update database
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute("DELETE FROM status")  # Clear old status
        c.execute("INSERT INTO status (status, message, eta, updated_by) VALUES (?, ?, ?, ?)",
                 (status, "", "", interaction.user.id))
        conn.commit()
        conn.close()
        
        # Update bot status
        if status == "online":
            await bot.change_presence(status=discord.Status.online, activity=discord.Game("🟢 Online"))
        elif status == "testing":
            await bot.change_presence(status=discord.Status.idle, activity=discord.Game("🟡 Testing"))
        else:  # offline
            await bot.change_presence(status=discord.Status.dnd, activity=discord.Game("🔴 Offline"))
        
        # Update channel name
        await update_status_channel_name(status)
        
        # Send status message to channel
        try:
            channel = bot.get_channel(STATUS_CHANNEL_ID)
            if channel:
                embed = discord.Embed(
                    title=f"{emoji} Status Opdatering",
                    description=f"**Status:** {status.title()}",
                    color=color,
                    timestamp=datetime.now()
                )
                embed.set_footer(text=f"Opdateret af {interaction.user.display_name}")
                await channel.send(embed=embed)
        except Exception as e:
            print(f"Error sending to status channel: {e}")
        
        await interaction.response.send_message(f"? Status Updatet to {emoji} **{status.title()}**", ephemeral=True)

# Status Modal for Testing and Offline
class StatusModal(discord.ui.Modal):
    def __init__(self, status_type, emoji, color):
        self.status_type = status_type
        self.emoji = emoji
        self.color = color
        super().__init__(title=f'Update Status - {status_type.title()}')

    message = discord.ui.TextInput(
        label='Message (optional)',
        placeholder='Write a message about status...',
        required=False,
        max_length=500,
        style=discord.TextStyle.paragraph
    )

    eta = discord.ui.TextInput(
        label='Expected time back online (optional)',
        placeholder='f.eks. "2 hours", "tomorrow at 10 am", "unknown"',
        required=False,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Update database
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute("DELETE FROM status")  # Clear old status
        c.execute("INSERT INTO status (status, message, eta, updated_by) VALUES (?, ?, ?, ?)",
                 (self.status_type, self.message.value, self.eta.value, interaction.user.id))
        conn.commit()
        conn.close()
        
        # Update bot status
        if self.status_type == "testing":
            await bot.change_presence(status=discord.Status.idle, activity=discord.Game("🟡 Testing"))
        else:  # offline
            await bot.change_presence(status=discord.Status.dnd, activity=discord.Game("🔴 Offline"))
        
        # Update channel name
        await update_status_channel_name(self.status_type)
        
        # Send status message to channel
        try:
            channel = bot.get_channel(STATUS_CHANNEL_ID)
            if channel:
                embed = discord.Embed(
                    title=f"{self.emoji} Status Updating",
                    description=f"**Status:** {self.status_type.title()}",
                    color=self.color,
                    timestamp=datetime.now()
                )
                
                if self.message.value:
                    embed.add_field(name="💬 Message", value=self.message.value, inline=False)
                
                if self.eta.value:
                    embed.add_field(name="⏰ Expected back online", value=self.eta.value, inline=False)
                
                embed.set_footer(text=f"Opdateret af {interaction.user.display_name}")
                await channel.send(embed=embed)
        except Exception as e:
            print(f"Error sending to status channel: {e}")
        
        status_text = f"? Status updatet to {self.emoji} **{self.status_type.title()}**"
        if self.message.value:
            status_text += f"\n💬 Message: {self.message.value}"
        if self.eta.value:
            status_text += f"\n⏰ ETA: {self.eta.value}"
        
        await interaction.response.send_message(status_text, ephemeral=True)

# All the Modal classes for admin functions
class GenerateKeyModal(discord.ui.Modal, title='Generate Key'):
    def __init__(self):
        super().__init__()

    max_time = discord.ui.TextInput(
        label='Max Attack Tid (Seconds)',
        placeholder='60',
        default='60',
        required=True,
        max_length=10
    )

    concurrent_attacks = discord.ui.TextInput(
        label='Concurrent Attacks',
        placeholder='1',
        default='1',
        required=True,
        max_length=5
    )

    vip = discord.ui.TextInput(
        label='VIP (Yes/no)',
        placeholder='No',
        default='No',
        required=True,
        max_length=3
    )

    expires_days = discord.ui.TextInput(
        label='Expires in (days, 0 = never)',
        placeholder='30',
        default='30',
        required=True,
        max_length=10
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            max_time_val = int(self.max_time.value)
            concurrent_val = int(self.concurrent_attacks.value)
            vip_val = 1 if self.vip.value.lower() in ['Yes', 'yes', '1', 'true'] else 0
            expires_days_val = int(self.expires_days.value)
            
            # Generate key
            key = generate_key()
            
            # Calculate expiration
            expires_at = None
            if expires_days_val > 0:
                expires_at = (datetime.now() + timedelta(days=expires_days_val)).isoformat()
            
            # Save to database
            conn = sqlite3.connect('bot_data.db')
            c = conn.cursor()
            c.execute("""INSERT INTO keys 
                         (key_id, created_by, max_time, concurrent_attacks, vip, expires_at)
                         VALUES (?, ?, ?, ?, ?, ?)""",
                     (key, interaction.user.id, max_time_val, concurrent_val, vip_val, expires_at))
            conn.commit()
            conn.close()
            
            embed = discord.Embed(title="🔑 Key Genereret", color=0x00ff00)
            embed.add_field(name="Key", value=f"`{key}`", inline=False)
            embed.add_field(name="Max Attack time", value=f"{max_time_val} seconds", inline=True)
            embed.add_field(name="Concurrent Attacks", value=str(concurrent_val), inline=True)
            embed.add_field(name="VIP", value="Yes" if vip_val else "No", inline=True)
            embed.add_field(name="Expires", value=expires_at[:10] if expires_at else "Never", inline=True)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message("? Invalid values! Check your inputs.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"? Fejl: {e}", ephemeral=True)

class EditAttackTimeModal(discord.ui.Modal, title='Edit Attack Time'):
    def __init__(self):
        super().__init__()

    user_id = discord.ui.TextInput(
        label='Bruger ID',
        placeholder='123456789012345678',
        required=True,
        max_length=20
    )

    new_time = discord.ui.TextInput(
        label='New Max Attack Time (seconds)',
        placeholder='120',
        required=True,
        max_length=10
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id_val = int(self.user_id.value)
            new_time_val = int(self.new_time.value)
            
            conn = sqlite3.connect('bot_data.db')
            c = conn.cursor()
            c.execute("UPDATE users SET max_time = ? WHERE user_id = ?", (new_time_val, user_id_val))
            
            if c.rowcount == 0:
                await interaction.response.send_message("? User not found!", ephemeral=True)
                conn.close()
                return
            
            conn.commit()
            conn.close()
            
            await interaction.response.send_message(f"? Attack time updated to {new_time_val} seconds for user {user_id_val}", ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message("? Invalid values!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"? Error: {e}", ephemeral=True)

class EditVipModal(discord.ui.Modal, title='Edit VIP Status'):
    def __init__(self):
        super().__init__()

    user_id = discord.ui.TextInput(
        label='Bruger ID',
        placeholder='123456789012345678',
        required=True,
        max_length=20
    )

    vip_status = discord.ui.TextInput(
        label='VIP Status (Yes/No)',
        placeholder='Yes',
        required=True,
        max_length=3
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id_val = int(self.user_id.value)
            vip_val = 1 if self.vip_status.value.lower() in ['Yes', 'yes', '1', 'true'] else 0
            
            conn = sqlite3.connect('bot_data.db')
            c = conn.cursor()
            c.execute("UPDATE users SET vip = ? WHERE user_id = ?", (vip_val, user_id_val))
            
            if c.rowcount == 0:
                await interaction.response.send_message("? User not found!", ephemeral=True)
                conn.close()
                return
            
            conn.commit()
            conn.close()
            
            vip_text = "VIP" if vip_val else "Standard"
            await interaction.response.send_message(f"? VIP status updated to {vip_text} for user {user_id_val}", ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message("? Invalid values!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"? Error: {e}", ephemeral=True)

class EditConcurrentModal(discord.ui.Modal, title='Edit Concurrent Attacks'):
    def __init__(self):
        super().__init__()

    user_id = discord.ui.TextInput(
        label='Bruger ID',
        placeholder='123456789012345678',
        required=True,
        max_length=20
    )

    concurrent = discord.ui.TextInput(
        label='Concurrent Attacks',
        placeholder='2',
        required=True,
        max_length=5
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id_val = int(self.user_id.value)
            concurrent_val = int(self.concurrent.value)
            
            conn = sqlite3.connect('bot_data.db')
            c = conn.cursor()
            c.execute("UPDATE users SET concurrent_attacks = ? WHERE user_id = ?", (concurrent_val, user_id_val))
            
            if c.rowcount == 0:
                await interaction.response.send_message("? User not found!", ephemeral=True)
                conn.close()
                return
            
            conn.commit()
            conn.close()
            
            await interaction.response.send_message(f"? Concurrent attacks updated to {concurrent_val} for user {user_id_val}", ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message("? Invalid values!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"? Error: {e}", ephemeral=True)

class AddStaffModal(discord.ui.Modal, title='Add Staff'):
    def __init__(self):
        super().__init__()

    user_id = discord.ui.TextInput(
        label='Bruger ID',
        placeholder='123456789012345678',
        required=True,
        max_length=20
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id_val = int(self.user_id.value)
            
            conn = sqlite3.connect('bot_data.db')
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO staff (user_id, added_by) VALUES (?, ?)",
                     (user_id_val, interaction.user.id))
            conn.commit()
            conn.close()
            
            try:
                user = await bot.fetch_user(user_id_val)
                username = user.name
            except:
                username = f"User ID: {user_id_val}"
            
            await interaction.response.send_message(f"? {username} is now a staff member!", ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message("? Invalid user ID!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"? Error: {e}", ephemeral=True)

class RemoveStaffModal(discord.ui.Modal, title='Remove Staff'):
    def __init__(self):
        super().__init__()

    user_id = discord.ui.TextInput(
        label='Bruger ID',
        placeholder='123456789012345678',
        required=True,
        max_length=20
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id_val = int(self.user_id.value)
            
            conn = sqlite3.connect('bot_data.db')
            c = conn.cursor()
            c.execute("DELETE FROM staff WHERE user_id = ?", (user_id_val,))
            
            if c.rowcount == 0:
                await interaction.response.send_message("? Users are not staff!", ephemeral=True)
                conn.close()
                return
            
            conn.commit()
            conn.close()
            
            try:
                user = await bot.fetch_user(user_id_val)
                username = user.name
            except:
                username = f"User ID: {user_id_val}"
            
            await interaction.response.send_message(f"? {username} is no longer staff!", ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message("? Invalid user ID!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"? Error: {e}", ephemeral=True)

class RemoveUserModal(discord.ui.Modal, title='Remove User'):
    def __init__(self):
        super().__init__()

    user_id = discord.ui.TextInput(
        label='Bruger ID',
        placeholder='123456789012345678',
        required=True,
        max_length=20
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id_val = int(self.user_id.value)
            
            conn = sqlite3.connect('bot_data.db')
            c = conn.cursor()
            c.execute("DELETE FROM users WHERE user_id = ?", (user_id_val,))
            
            if c.rowcount == 0:
                await interaction.response.send_message("? User not found!", ephemeral=True)
                conn.close()
                return
            
            conn.commit()
            conn.close()
            
            await interaction.response.send_message(f"? User {user_id_val} removed from the system!", ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message("? Invalid user ID!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"? Fejl: {e}", ephemeral=True)

class AddTimeModal(discord.ui.Modal, title='Extend User'):
    def __init__(self):
        super().__init__()

    user_id = discord.ui.TextInput(
        label='Bruger ID',
        placeholder='123456789012345678',
        required=True,
        max_length=20
    )

    days = discord.ui.TextInput(
        label='Add days',
        placeholder='30',
        required=True,
        max_length=10
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id_val = int(self.user_id.value)
            days_val = int(self.days.value)
            
            conn = sqlite3.connect('bot_data.db')
            c = conn.cursor()
            
            # Get current expiration
            c.execute("SELECT expires_at FROM users WHERE user_id = ?", (user_id_val,))
            result = c.fetchone()
            
            if not result:
                await interaction.response.send_message("? Bruger ikke fundet!", ephemeral=True)
                conn.close()
                return
            
            current_expires = result[0]
            
            # Calculate new expiration
            if current_expires:
                current_date = datetime.fromisoformat(current_expires)
                new_expires = current_date + timedelta(days=days_val)
            else:
                new_expires = datetime.now() + timedelta(days=days_val)
            
            # Update database
            c.execute("UPDATE users SET expires_at = ? WHERE user_id = ?", 
                     (new_expires.isoformat(), user_id_val))
            conn.commit()
            conn.close()
            
            await interaction.response.send_message(f"? Added {days_val} days to user {user_id_val}. New Expiration Date: {new_expires.strftime('%Y-%m-%d')}", ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message("? Invalid values!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"? Error: {e}", ephemeral=True)

# Add Admin Modal (Kun super admin kan bruge)
class AddAdminModal(discord.ui.Modal, title='Add Admin'):
    def __init__(self):
        super().__init__()

    user_id = discord.ui.TextInput(
        label='Bruger ID',
        placeholder='123456789012345678',
        required=True,
        max_length=20
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id_val = int(self.user_id.value)
            
            conn = sqlite3.connect('bot_data.db')
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO admins (user_id, added_by) VALUES (?, ?)",
                     (user_id_val, interaction.user.id))
            conn.commit()
            conn.close()
            
            try:
                user = await bot.fetch_user(user_id_val)
                username = user.name
            except:
                username = f"User ID: {user_id_val}"
            
            embed = discord.Embed(title="👑 Admin Added", color=0x00ff00)
            embed.add_field(name="User", value=username, inline=False)
            embed.add_field(name="User ID", value=str(user_id_val), inline=False)
            embed.add_field(name="Added by", value=interaction.user.mention, inline=False)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message("? Invalid user ID!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"? Error: {e}", ephemeral=True)

# Remove Admin Modal (Kun super admin kan bruge)
class RemoveAdminModal(discord.ui.Modal, title='Remove Admin'):
    def __init__(self):
        super().__init__()

    user_id = discord.ui.TextInput(
        label='Bruger ID',
        placeholder='123456789012345678',
        required=True,
        max_length=20
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id_val = int(self.user_id.value)
            
            # Check if user is super admin (can't remove super admin)
            if is_super_admin(user_id_val):
                await interaction.response.send_message("? Unable to remove Super Admin!", ephemeral=True)
                return
            
            conn = sqlite3.connect('bot_data.db')
            c = conn.cursor()
            c.execute("DELETE FROM admins WHERE user_id = ?", (user_id_val,))
            
            if c.rowcount == 0:
                await interaction.response.send_message("? User is not admin!", ephemeral=True)
                conn.close()
                return
            
            conn.commit()
            conn.close()
            
            try:
                user = await bot.fetch_user(user_id_val)
                username = user.name
            except:
                username = f"User ID: {user_id_val}"
            
            embed = discord.Embed(title="🗑️ Admin Removed", color=0xff0000)
            embed.add_field(name="User", value=username, inline=False)
            embed.add_field(name="User ID", value=str(user_id_val), inline=False)
            embed.add_field(name="Fjernet af", value=interaction.user.mention, inline=False)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message("? Invalid user ID!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"? Error: {e}", ephemeral=True)

# Admin Panel View
class AdminPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label='📊 Update Status', style=discord.ButtonStyle.primary)
    async def update_status_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = StatusSelectionView()
        embed = discord.Embed(title="📊 Update Bot Status", description="Choose new status for the bot:", color=0x0099ff)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label='🔑 Generate Key', style=discord.ButtonStyle.green)
    async def generate_key_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = GenerateKeyModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='⏰ Edit Attack Time', style=discord.ButtonStyle.secondary)
    async def edit_time_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = EditAttackTimeModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='👑 Edit VIP', style=discord.ButtonStyle.secondary)
    async def edit_vip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = EditVipModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='⚡ Edit Concurrent', style=discord.ButtonStyle.secondary)
    async def edit_concurrent_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = EditConcurrentModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='👥 Add Staff', style=discord.ButtonStyle.green)
    async def add_staff_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = AddStaffModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='👥 Remove Staff', style=discord.ButtonStyle.danger)
    async def remove_staff_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = RemoveStaffModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='👤 Remove Users', style=discord.ButtonStyle.danger)
    async def remove_user_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = RemoveUserModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='📅 Extend User', style=discord.ButtonStyle.green)
    async def add_time_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = AddTimeModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='🔍 See Keys', style=discord.ButtonStyle.secondary)
    async def view_keys_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute("SELECT * FROM keys ORDER BY created_at DESC LIMIT 10")
        keys = c.fetchall()
        conn.close()
        
        embed = discord.Embed(title="🔑 Key Overview", color=0x00ff00)
        
        if not keys:
            embed.description = "No keys found"
        else:
            for key in keys:
                key_id, created_by, max_time, concurrent, vip, expires_at, used_by, created_at = key
                status = "Used" if used_by else "Available"
                vip_text = "Yes" if vip else "No"
                embed.add_field(
                    name=f"Key: {key_id[:8]}...",
                    value=f"Status: {status}\nVIP: {vip_text}\nMax tid: {max_time}s\nConcurrent: {concurrent}",
                    inline=True
                )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label='👥 See users', style=discord.ButtonStyle.secondary)
    async def view_users_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users ORDER BY created_at DESC LIMIT 10")
        users = c.fetchall()
        conn.close()
        
        embed = discord.Emembed(title="👥 User Overview", color=0x00ff00)
        
        if not users:
            embed.description = "No users found"
        else:
            for user in users:
                user_id, key_used, vip, max_time, concurrent, expires_at, created_at = user
                try:
                    discord_user = await bot.fetch_user(user_id)
                    username = discord_user.name
                except:
                    username = f"User ID: {user_id}"
                
                vip_text = "Yes" if vip else "No"
                embed.add_field(
                    name=f"{username} ({user_id})",
                    value=f"VIP: {vip_text}\nMax tid: {max_time}s\nConcurrent: {concurrent}\nExpires: {expires_at[:10] if expires_at else 'Never'}",
                    inline=True
                )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label='📈 Statistik', style=discord.ButtonStyle.primary)
    async def stats_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        
        # Get statistics
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM keys")
        total_keys = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM keys WHERE used_by IS NOT NULL")
        used_keys = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM users WHERE vip = 1")
        vip_users = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM staff")
        staff_count = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM admins")
        admin_count = c.fetchone()[0]
        
        conn.close()
        
        embed = discord.Embed(title="📈 System Statistik", color=0x0099ff)
        embed.add_field(name="👥 Total Users", value=str(total_users), inline=True)
        embed.add_field(name="👑 VIP Users", value=str(vip_users), inline=True)
        embed.add_field(name="🔑 Total Keys", value=str(total_keys), inline=True)
        embed.add_field(name="✅ Used Keys", value=str(used_keys), inline=True)
        embed.add_field(name="🔓 Available Keys", value=str(total_keys - used_keys), inline=True)
        embed.add_field(name="👥 Staff Members", value=str(staff_count), inline=True)
        embed.add_field(name="👑 Admins", value=str(admin_count), inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

# Super Admin buttons (only visible to super admin)
class SuperAdminView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label='👑 Add Admin', style=discord.ButtonStyle.green)
    async def add_admin_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = AddAdminModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='🗑️ Remove Admin', style=discord.ButtonStyle.danger)
    async def remove_admin_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = RemoveAdminModal()
        await interaction.response.send_modal(modal)

# Staff Panel View
class StaffPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label='🔑 generates Key', style=discord.ButtonStyle.green)
    async def generate_key_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = GenerateKeyModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='🔍 Se Keys', style=discord.ButtonStyle.secondary)
    async def view_keys_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute("SELECT * FROM keys ORDER BY created_at DESC LIMIT 10")
        keys = c.fetchall()
        conn.close()
        
        embed = discord.Embed(title="🔑 Key Overview", color=0x00ff00)
        
        if not keys:
            embed.description = "No keys found"
        else:
            for key in keys:
                key_id, created_by, max_time, concurrent, vip, expires_at, used_by, created_at = key
                status = "Used" if used_by else "Available"
                vip_text = "Yes" if vip else "No"
                embed.add_field(
                    name=f"Key: {key_id[:8]}...",
                    value=f"Status: {status}\nVIP: {vip_text}\nMax tid: {max_time}s\nConcurrent: {concurrent}",
                    inline=True
                )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label='👥 See Users', style=discord.ButtonStyle.secondary)
    async def view_users_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users ORDER BY created_at DESC LIMIT 10")
        users = c.fetchall()
        conn.close()
        
        embed = discord.Embed(title="👥 User Overview", color=0x00ff00)
        
        if not users:
            embed.description = "No users found"
        else:
            for user in users:
                user_id, key_used, vip, max_time, concurrent, expires_at, created_at = user
                try:
                    discord_user = await bot.fetch_user(user_id)
                    username = discord_user.name
                except:
                    username = f"User ID: {user_id}"
                
                vip_text = "Yes" if vip else "No"
                embed.add_field(
                    name=f"{username} ({user_id})",
                    value=f"VIP: {vip_text}\nMax tid: {max_time}s\nConcurrent: {concurrent}\nExpires: {expires_at[:10] if expires_at else 'Never'}",
                    inline=True
                )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label='📈 Statistik', style=discord.ButtonStyle.primary)
    async def stats_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        
        # Get statistics
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM keys")
        total_keys = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM keys WHERE used_by IS NOT NULL")
        used_keys = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM users WHERE vip = 1")
        vip_users = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM staff")
        staff_count = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM admins")
        admin_count = c.fetchone()[0]
        
        conn.close()
        
        embed = discord.Embed(title="📈 System Statistik", color=0x0099ff)
        embed.add_field(name="👥 Total Users", value=str(total_users), inline=True)
        embed.add_field(name="👑 VIP Users", value=str(vip_users), inline=True)
        embed.add_field(name="🔑 Total Keys", value=str(total_keys), inline=True)
        embed.add_field(name="✅ Used Keys", value=str(used_keys), inline=True)
        embed.add_field(name="🔓 Available Keys", value=str(total_keys - used_keys), inline=True)
        embed.add_field(name="👥 Staff Member", value=str(staff_count), inline=True)
        embed.add_field(name="👑 Admins", value=str(admin_count), inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

# Attack command with method autocomplete
@bot.tree.command(name="attack", description="Start a attack")
async def attack(interaction: discord.Interaction, 
                host: str, 
                port: int, 
                time: int, 
                method: str):
    
    # Check user permissions
    user_perms = get_user_permissions(interaction.user.id)
    if not user_perms:
        await interaction.response.send_message("? You do not have access to this bot! Use `/redeem` with a key first.", ephemeral=True)
        return
    
    user_id, key_used, vip, max_time, concurrent_attacks, expires_at, created_at = user_perms
    
    # Check if user has expired
    if expires_at and datetime.now() > datetime.fromisoformat(expires_at):
        await interaction.response.send_message("? Your access has expired! Contact an admin.", ephemeral=True)
        return
    
    # Validate method (case insensitive)
    method_lower = method.lower()
    if method_lower not in ATTACK_METHODS:
        available_methods = ", ".join(ATTACK_METHODS.keys())
        await interaction.response.send_message(f"? Invalid method! Available methods: {available_methods}", ephemeral=True)
        return
    
    # Check VIP requirement
    method_info = ATTACK_METHODS[method_lower]
    if method_info["vip"] and not vip:
        await interaction.response.send_message(f"? Metoden `{method_lower}` requires VIP access!", ephemeral=True)
        return
    
    # Validate time
    if time > max_time:
        await interaction.response.send_message(f"? Max attack time is {max_time} seconds for your account!", ephemeral=True)
        return
    
    if time < 1:
        await interaction.response.send_message("? Attack time must be at least 1 second!", ephemeral=True)
        return
    
    # Validate port
    if port < 1 or port > 65535:
        await interaction.response.send_message("? Port must be between 1 and 65535!", ephemeral=True)
        return
    
    # Send attack request to API
    try:
        api_url = method_info["api"].format(host=host, port=port, time=time)
        print(f"Sending attack request to: {api_url}")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=10) as response:
                response_text = await response.text()
                print(f"API Response: {response.status} - {response_text}")
        
        # Always show success message regardless of API response
        embed = discord.Embed(title="⚡ Attack Startet!", color=0x00ff00)
        embed.add_field(name="🎯 Target", value=f"{host}:{port}", inline=True)
        embed.add_field(name="⏰ Tid", value=f"{time} seconds", inline=True)
        embed.add_field(name="🔧 Metode", value=method_lower.upper(), inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    except asyncio.TimeoutError:
        await interaction.response.send_message("⏱️ API timeout - attack may still have started", ephemeral=True)
    except Exception as e:
        print(f"API Error: {e}")
        # Still show success message even if API fails
        embed = discord.Embed(title="⚡ Attack Startet!", color=0x00ff00)
        embed.add_field(name="🎯 Target", value=f"{host}:{port}", inline=True)
        embed.add_field(name="⏰ Tid", value=f"{time} seconds", inline=True)
        embed.add_field(name="🔧 Metode", value=method_lower.upper(), inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

# Autocomplete for attack methods
@attack.autocomplete('method')
async def method_autocomplete(interaction: discord.Interaction, current: str):
    # Get user permissions to check VIP status
    user_perms = get_user_permissions(interaction.user.id)
    if not user_perms:
        return [app_commands.Choice(name="You must first use /redeem", value="invalid")]
    
    user_id, key_used, vip, max_time, concurrent_attacks, expires_at, created_at = user_perms
    
    # Filter methods based on VIP status and current input
    choices = []
    for method, info in ATTACK_METHODS.items():
        if current.lower() in method.lower():
            if info["vip"] and not vip:
                choices.append(app_commands.Choice(name=f"{method} (VIP Required)", value=method))
            else:
                choices.append(app_commands.Choice(name=method, value=method))
    
    # Return max 25 choices (Discord limit)
    return choices[:25]

# Redeem key command
@bot.tree.command(name="redeem", description="Redeem a key")
async def redeem(interaction: discord.Interaction, key: str):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    
    # Check if key exists and is unused
    c.execute("SELECT * FROM keys WHERE key_id = ?", (key,))
    key_data = c.fetchone()
    
    if not key_data:
        await interaction.response.send_message("? Invalid key!", ephemeral=True)
        conn.close()
        return
    
    key_id, created_by, max_time, concurrent_attacks, vip, expires_at, used_by, created_at = key_data
    
    if used_by:
        await interaction.response.send_message("? This key has already been used!", ephemeral=True)
        conn.close()
        return
    
    # Check if key has expired
    if expires_at and datetime.now() > datetime.fromisoformat(expires_at):
        await interaction.response.send_message("? This key is Expired!", ephemeral=True)
        conn.close()
        return
    
    # Check if user already has access
    c.execute("SELECT user_id FROM users WHERE user_id = ?", (interaction.user.id,))
    existing_user = c.fetchone()
    
    if existing_user:
        await interaction.response.send_message("? You already have access to the bot!", ephemeral=True)
        conn.close()
        return
    
    # Mark key as used and add user
    c.execute("UPDATE keys SET used_by = ? WHERE key_id = ?", (interaction.user.id, key))
    c.execute("""INSERT INTO users 
                 (user_id, key_used, vip, max_time, concurrent_attacks, expires_at) 
                 VALUES (?, ?, ?, ?, ?, ?)""",
             (interaction.user.id, key, vip, max_time, concurrent_attacks, expires_at))
    
    conn.commit()
    conn.close()
    
    embed = discord.Embed(title="✅ Key Redeemed!", color=0x00ff00)
    embed.add_field(name="VIP Status", value="👑 Yes" if vip else "❌ No", inline=True)
    embed.add_field(name="Max Attack time", value=f"{max_time} seconds", inline=True)
    embed.add_field(name="Concurrent Attacks", value=str(concurrent_attacks), inline=True)
    embed.add_field(name="Expires", value=expires_at[:10] if expires_at else "Aldrig", inline=True)
    embed.add_field(name="Next step", value="Brug `/methods` to see available attack methods", inline=False)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Admin panel command
@bot.tree.command(name="admin", description="Admin panel")
async def admin_panel(interaction: discord.Interaction):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("? You do not have access to the admin panel.!", ephemeral=True)
        return
    
    embed = discord.Embed(title="👑 Admin Panel", description="Administrator control panel", color=0xff0000)
    embed.add_field(name="📊 Status Management", value="Update bot status", inline=True)
    embed.add_field(name="🔑 Key Management", value="Generate and manage keys", inline=True)
    embed.add_field(name="👤 User Management", value="Manage users", inline=True)
    embed.add_field(name="👥 Staff Management", value="Add/remove staff", inline=True)
    embed.add_field(name="📈 Statistics", value="See detailed statistics", inline=True)
    
    view = AdminPanelView()
    
    # Add super admin buttons if user is super admin
    if is_super_admin(interaction.user.id):
        embed.add_field(name="👑 Super Admin", value="Admin management", inline=True)
        # Create a combined view with both admin and super admin buttons
        super_view = SuperAdminView()
        # Add super admin buttons to the main view
        for item in super_view.children:
            view.add_item(item)
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# Staff panel command
@bot.tree.command(name="staff", description="Staff panel")
async def staff_panel(interaction: discord.Interaction):
    if not is_staff(interaction.user.id):
        await interaction.response.send_message("? You do not have access to the staff panel.!", ephemeral=True)
        return
    
    embed = discord.Embed(title="👥 Staff Panel", description="Staff control panel", color=0x0099ff)
    embed.add_field(name="🔑 Key Management", value="Generate and view keys", inline=True)
    embed.add_field(name="👤 User Overview", value="See users and statistics", inline=True)
    embed.add_field(name="📈 Statistics", value="System statistics and overview", inline=True)
    
    view = StaffPanelView()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# Methods command
@bot.tree.command(name="methods", description="See available attack methods")
async def methods(interaction: discord.Interaction):
    user_perms = get_user_permissions(interaction.user.id)
    if not user_perms:
        await interaction.response.send_message("? You do not have access to this bot.! Brug `/redeem` with key first.", ephemeral=True)
        return
    
    user_id, key_used, vip, max_time, concurrent_attacks, expires_at, created_at = user_perms
    
    embed = discord.Embed(title="🔧 Attack Metoder", color=0x0099ff)
    
    free_methods = []
    vip_methods = []
    
    for method, info in ATTACK_METHODS.items():
        if info["vip"]:
            vip_methods.append(method)
        else:
            free_methods.append(method)
    
    # Show free methods
    if free_methods:
        embed.add_field(
            name="🔓 Normal Metoder", 
            value="```" + ", ".join(free_methods) + "```", 
            inline=False
        )
    
    # Show VIP methods
    if vip_methods:
        if vip:
            embed.add_field(
                name="👑 VIP Metoder (you have access)", 
                value="```" + ", ".join(vip_methods) + "```", 
                inline=False
            )
        else:
            embed.add_field(
                name="👑 VIP Metoder (you need VIP)", 
                value="```" + ", ".join(vip_methods) + "```", 
                inline=False
            )
    
    # User status
    if vip:
        embed.add_field(name="Din Status", value="👑 VIP - You have access to all methods!", inline=False)
    else:
        embed.add_field(name="Din Status", value="🔓 Standard - Only normal metoder", inline=False)
    
    embed.add_field(name="Max Attack Tid", value=f"{max_time} seconds", inline=True)
    embed.add_field(name="Concurrent Attacks", value=str(concurrent_attacks), inline=True)
    
    # Usage example
    embed.add_field(
        name="💡 Eksempel", 
        value="`/attack 1.1.1.1 80 60 udp`", 
        inline=False
    )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Profile command
@bot.tree.command(name="profile", description="See your profil")
async def profile(interaction: discord.Interaction):
    user_perms = get_user_permissions(interaction.user.id)
    if not user_perms:
        await interaction.response.send_message("? You do not have access to this bot! Use `/redeem` with key first.", ephemeral=True)
        return
    
    user_id, key_used, vip, max_time, concurrent_attacks, expires_at, created_at = user_perms
    
    embed = discord.Embed(title="👤 Your Profil", color=0x0099ff)
    embed.add_field(name="Bruger", value=interaction.user.mention, inline=True)
    embed.add_field(name="VIP Status", value="👑 Yes" if vip else "❌ No", inline=True)
    embed.add_field(name="Max Attack Tid", value=f"{max_time} seconds", inline=True)
    embed.add_field(name="Concurrent Attacks", value=str(concurrent_attacks), inline=True)
    embed.add_field(name="Key Used", value=f"`{key_used[:8]}...`", inline=True)
    embed.add_field(name="Expires", value=expires_at[:10] if expires_at else "Never", inline=True)
    embed.add_field(name="Created", value=created_at[:10], inline=True)
    
    # Check if user is staff or admin
    roles = []
    if is_super_admin(interaction.user.id):
        roles.append("👑 Super Admin")
    elif is_admin(interaction.user.id):
        roles.append("👑 Admin")
    elif is_staff(interaction.user.id):
        roles.append("👥 Staff")
    
    if roles:
        embed.add_field(name="Roles", value=", ".join(roles), inline=False)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Status command
@bot.tree.command(name="status", description="Se bot status")
async def status_command(interaction: discord.Interaction):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    
    try:
        c.execute("SELECT * FROM status ORDER BY updated_at DESC LIMIT 1")
        status_data = c.fetchone()
        
        if status_data:
            status_id, status, message, eta, updated_by, updated_at = status_data
            
            # Set color based on status
            if status == "online":
                color = 0x00ff00
                emoji = "🟢"
            elif status == "testing":
                color = 0xffff00
                emoji = "🟡"
            else:  # offline
                color = 0xff0000
                emoji = "🔴"
            
            embed = discord.Embed(
                title=f"{emoji} Bot Status",
                description=f"**Status:** {status.title()}",
                color=color,
                timestamp=datetime.fromisoformat(updated_at)
            )
            
            if message:
                embed.add_field(name="💬 Message", value=message, inline=False)
            
            if eta:
                embed.add_field(name="⏰ Expected back online", value=eta, inline=False)
            
            try:
                updated_user = await bot.fetch_user(updated_by)
                embed.set_footer(text=f"Last updated by {updated_user.name}")
            except:
                embed.set_footer(text=f"Last updated by User ID: {updated_by}")
        else:
            embed = discord.Embed(
                title="🟢 Bot Status",
                description="**Status:** Online (Standard)",
                color=0x00ff00
            )
            embed.set_footer(text="No status updates found")
        
    except Exception as e:
        embed = discord.Embed(
            title="❌ Status error",
            description="Could not retrieve status information",
            color=0xff0000
        )
        print(f"Status command error: {e}")
    finally:
        conn.close()
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Help command
@bot.tree.command(name="help", description="Help and command overview")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(title="❓ Help & Commands", color=0x0099ff)
    
    # Basic commands for all users
    embed.add_field(
        name="🔰 Basic Commands",
        value="`/redeem <key>` - Redem a key\n`/profile` - See your profile\n`/status` - See bot status\n`/methods` - See available methods\n`/help` - Show this Help",
        inline=False
    )
    
    # Check if user has access
    user_perms = get_user_permissions(interaction.user.id)
    if user_perms:
        embed.add_field(
            name="⚡ Attack Commander",
            value="`/attack <host> <port> <time> <method>` - Start a attack",
            inline=False
        )
    
    # Staff commands
    if is_staff(interaction.user.id):
        embed.add_field(
            name="👥 Staff Commands",
            value="`/staff` - Ĺbn staff panel",
            inline=False
        )
    
    # Admin commands
    if is_admin(interaction.user.id):
        embed.add_field(
            name="👑 Admin Commands",
            value="`/admin` - Ĺbn admin panel",
            inline=False
        )
    
    embed.add_field(
        name="💡 Attack Example",
        value="`/attack 1.1.1.1 80 60 udp`\nAttacker 1.1.1.1:80 for 60 seconds with the UDP method",
        inline=False
    )
    
    embed.add_field(
        name="ℹ️ Information",
        value="• All commands are private (only you can see them)\n• Contact staff for help or keys\n• VIP provides access to more methods and longer attack time\n• Brug `/methods` to see all available attack methods",
        inline=False
    )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.event
async def on_ready():
    print(f'{bot.user} Is online!')
    print(f'Bot ID: {bot.user.id}')
    print('---')
    
    # Initialize database
    init_db()
    
    # Set initial status
    await bot.change_presence(status=discord.Status.online, activity=discord.Game("🟢 Online"))
    
    # Update status channel name
    await update_status_channel_name("online")
    
    print("Bot er klar til brug!")
    print("Tilgængelig kommandoer:")
    print("- /attack - Start a attack")
    print("- /redeem - Redem a key")
    print("- /methods - See attack metoder")
    print("- /profile - See your profil")
    print("- /status - See bot status")
    print("- /help - help")
    print("- /staff - Staff panel")
    print("- /admin - Admin panel")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    print(f'Error: {error}')

# Run the bot
if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except Exception as e:
        print(f"? Error starting bot: {e}")
        print("Check that the TOKEN is correct and that the bot has the necessary permissions")


# Made by Sofus...