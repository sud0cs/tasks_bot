import discord
from discord.ext.commands import bot, Context
import tasks
import asyncio
import json
import trello
class Bot():
    def __init__(self, prefix:str, token:str, notification_channel_name:str, trello_api_key:str, trello_token:str) -> None:
        intents = discord.Intents.all()
        self.bot = bot.Bot(command_prefix=prefix, intents=intents)
        self.bot.on_guild_available = self.on_guild_available
        self.token = token
        self.notification_channel_name = notification_channel_name
        self.trello_boards_path = 'guild_trello_boards.json'
        self.trello_api_key = trello_api_key
        self.trello_token = trello_token
        self.taskmanagers = {}
        try:
            self.guild_trello_board = json.loads(open(self.trello_boards_path, 'r').read())
        except:
            self.guild_trello_board = {}
        self.task()
        self.list_tasks()
        self.set_undone()
        self.set_done()
        self.notify_every()
        self.assign_trello()
        self.sync_local()
        self.sync_trello()
        self.assign()
        self.unassign()

    def task(self):
        @self.bot.command()
        async def task(context:Context, *args:discord.User|discord.Role):
            self.taskmanagers[context.guild.id].create_task(context, args)
        return task

    def list_tasks(self):
        @self.bot.command()
        async def list_tasks(context:Context, *args):
            self.taskmanagers[context.guild.id].list_tasks(context)
        return list_tasks

    def set_done(self):
        @self.bot.command()
        async def set_done(context:Context, *args):
            self.taskmanagers[context.guild.id].set_done(context, True)
        return set_done

    def set_undone(self):
        @self.bot.command()
        async def set_undone(context:Context, *args):
            self.taskmanagers[context.guild.id].set_done(context, False)
        return set_undone

    def notify_every(self):
        @self.bot.command()
        async def notify_every(context:Context, rate:int, measure:str):
            measure = measure.upper()
            if measure.endswith('S'):
                measure = measure[:len(measure)-1]
            self.taskmanagers[context.guild.id].create_notification(context, rate, measure)
        return notify_every
    
    def assign_trello(self):
        @self.bot.command()
        async def assign_trello(context:Context, trello_board:str|None=None):
            self.guild_trello_board[str(context.guild.id)] = trello_board
            self.taskmanagers[context.guild.id].set_trello(trello.Trello(self.trello_api_key, self.trello_token, trello_board) if trello_board is not None else None)
            with open(self.trello_boards_path ,'w') as file:
                file.write(json.dumps(self.guild_trello_board))
        return assign_trello

    def sync_local(self):
        @self.bot.command()
        async def sync_local(context:Context):
            self.taskmanagers[context.guild.id].sync_local()
        return sync_local

    def sync_trello(self):
        @self.bot.command()
        async def sync_trello(context:Context):
            self.taskmanagers[context.guild.id].sync_trello()
        return sync_trello

    def assign(self):
        @self.bot.command()
        async def assign(context:Context, *args:discord.User|discord.Role):
            self.taskmanagers[context.guild.id].assign_task(context, args)
        return assign

    def unassign(self):
        @self.bot.command()
        async def unassign(context:Context, *args:discord.User|discord.Role):
            self.taskmanagers[context.guild.id].unassign_task(context, args)
        return unassign

    async def on_guild_available(self, guild):
        notification_channel = discord.utils.get(guild.channels, name=self.notification_channel_name)
        trello_id = self.guild_trello_board.get(str(guild.id), None)
        trello_board = trello.Trello(self.trello_api_key, self.trello_token, trello_id) if trello_id is not None else None
        self.taskmanagers[guild.id] = tasks.TaskManager(asyncio.get_event_loop(), guild.id, notification_channel, trello_board)
    
    def start(self):
        self.bot.run(token=self.token)
