#Imports
from collections.abc import Iterable
import pickle
import asyncio
import discord
import os
import datetime
import trello
import math

#Class to handle messages

class Message():

    #Subclass to handle message content.
    
    class Content():
        def __init__(self, content=None, embed=None, view=None):
            self.content = content
            self.embed = embed
            self.view = view

    def __init__(self, loop, channel = None):
        self.loop = loop
        self.channel = channel
        self.discord_message = None
        self.extra = None

    #Method to bind callbacks to buttons. This buttons variable name must end with _button . Example: play_button
    #button must be a string or an Iterable containing strings. This strings have to be the button variable name.
    #callback must be the method callback or an Iterable containing the methods in the same order as the button iterable.
    #EXAMPLES:


    #bind_button('play', self.play_callback)
    #bind_button('play_button', self.play_callback)
    #bind_button(('play', 'stop'), (self.play_callback, self.stop_calback))

    def bind_button(self, button, callback, prefix='_button'):
        if isinstance(button, Iterable) and not isinstance(button, str):
            if isinstance(callback, Iterable):
                button = list(button)
                if len(button) == len(callback):
                    for i in range(len(button)):
                        button[i] = button[i][:len(button[i])-len(prefix)] if button[i].endswith(prefix) else button[i]
                        _str = button[i] + prefix
                        _ = vars(self)[_str]
                        _.callback = callback[i]
                        _.interaction_check = self._interaction_check_callback
                else:
                    raise ValueError('callback must have the same amount of parameters as button')
            else:
                raise ValueError('callback must be the same type as button')
        elif isinstance(button, str):
            button = button[:len(button)-len(prefix)] if button.endswith(prefix) else button
            button += prefix
            _ = vars(self)[button]
            _.callback = callback
            _.interaction_check = self._interaction_check_callback
        else:
            raise ValueError('Button must be either a string or a collection of strings.\nExample: ("play", "stop_button") or "play"')
    
    async def _interaction_check_callback(self, interaction):
        interaction.extras = self.extra
        return interaction
    
    def set_extra(self, **kwargs):
        self.extra = kwargs

    #Method to send the message
    def _send(self, content:Content|None, delete_last = True): 
        if content:
            if self.discord_message is not None and delete_last:
                asyncio.run_coroutine_threadsafe(self.discord_message.delete(), loop=self.loop)
            asyncio.run_coroutine_threadsafe(self.channel.send(content=content.content, embed=content.embed , view=content.view), loop=self.loop).add_done_callback(self.future_callback)

    def _update(self, content:Content|None):
        if content:
            if self.discord_message is not None:
                asyncio.run_coroutine_threadsafe(self.discord_message.edit(content=content.content, embed=content.embed , view=content.view), loop=self.loop).add_done_callback(self.future_callback)

    #Delete message
    def delete(self):
        asyncio.run_coroutine_threadsafe(self.discord_message.delete(), loop=self.loop)

    #Callback to handle the future from the _send method and set self.discord_message
    def future_callback(self, future): 
        self.discord_message = future.result()


    # Method to update message. Must be overwritten
    def update(self, *args, **kwargs): 
        pass
    # Method to create the message and send it to discord via _send. This method must return a Content instance. Must be overwritten.
    def _build(self) -> Content:
        pass

    # Method to build and send the message. Must be overwritten
    def send(self) -> None:
        pass

class CustomModal(discord.ui.Modal):
    def __init__(self, title=''):
        super().__init__(title=title)
        self.extra = None

    def set_extra(self, **kwargs):
        self.extra = kwargs

    def set_submit_callback(self, callback):
        setattr(self, 'on_submit', callback)

    async def interaction_check(self, interaction):
        interaction.extras = self.extra
        return interaction

    def get_items_id(self):
        return [i.custom_id for i in vars(self).values() if isinstance(i, discord.ui.Item)]

class TaskModal(CustomModal):
    title_input = discord.ui.TextInput(label='Title', custom_id='title')
    description_input = discord.ui.TextInput(label='Description', custom_id='description', style=discord.TextStyle.paragraph, required=False)
    start_date = discord.ui.TextInput(label='Start Date', custom_id='start_date', placeholder='dd/mm/yyyy (defaults to today if empty)', required=False)
    end_date = discord.ui.TextInput(label='End Date', custom_id='end_date', placeholder='dd/mm/yyyy', required=False)

    def set_data(self, title:str, description:str, start_date:datetime.datetime|None|str, end_date:datetime.datetime|None|str):
        self.title_input.default = title
        self.description_input.default = description
        try:
            self.start_date.default = start_date.strftime('%d/%m/%Y')
        except:
            self.start_date.default = ''
        try:
            self.end_date.default = end_date.strftime('%d/%m/%Y')
        except:
            self.end_date.default = ''
        return self

class TaskListMessage(Message):
    def __init__(self, loop, channel=None):
        super().__init__(loop, channel)
        self.view = discord.ui.View()
        self.previous_button = discord.ui.Button(label='<')
        self.next_button = discord.ui.Button(label='>')
        self.max_column_width = 40
        self.page_index = 0
        self.tasks = []
        self.pages = []
        self.bind_button(('previous', 'next'), (self.previous_button_callback, self.next_button_callback))
    def write_column(self, text, max_width):
        text = text.split(' ')
        line = ''
        lines = []
        for i in text:
            if len(i) + len(line) <= max_width:
                line += ' ' + i
            elif len(i) >= max_width:
                if line != '':
                    lines.append(line.strip())
                count = int(math.ceil(len(i)/max_width))
                for j in range(count):
                    line = i[j*max_width:(j*max_width)+max_width]
                    if j!=count-1:
                        lines.append(line.strip())
            else:
                lines.append(line.strip())
                line = i
        lines.append(line)
        return lines

    def _gen_pages(self, tasks):
        pages = []
        content = '`'
        content+='|Title' + ' '*(self.max_column_width-len('title')) +'|Description' + ' '*(self.max_column_width-len('description')) + '|Is Done' + '|Start Date' + '|End Date  ' + '|Assignees' + '|`\n'
        for task in tasks:
            task_text = ''
            description = task.get_description() if task.get_description() != "" and task.get_description() is not None else "-"
            description_list = self.write_column(description, self.max_column_width)
            title_list = self.write_column(task.get_title(), self.max_column_width)
            assignees = []
            for i in task.get_assignees():
                data = i.split(":")
                assignees.append(f'{data[1]}') if data[0] == 'Role' else assignees.append(f'<@{data[1]}>')
            assignees = " ".join(assignees)
            max_length = max(len(description_list), len(title_list))
            for i in range(max_length):
                line = ''
                for j in (title_list, description_list):
                    try:
                        line+='|' + j[i] + ' '*(self.max_column_width-len(j[i]))
                    except Exception as e:
                        line+= '|' + ' '*self.max_column_width
                if i==0:
                    start_date = task.get_start_date().strftime('%d/%m/%Y')
                    end_date = task.get_end_date()
                    end_date = end_date.strftime('%d/%m/%Y') if end_date is not None else '-'
                    line='`'+line + '|' + f'{task.is_done()}' + ' '*(len('is done') - len(str(task.is_done()))) + '|' + start_date + ' '*(len('start date')-len(start_date)) + '|' + end_date + ' '*(10-len(end_date)) +'|`' + assignees + '\n'
                else:
                    line='`'+line+'|`'+'\n'
                task_text+=line
            if len(content)+len(task_text)>2000:
                pages.append(content)
                content = '`'
                content+='|Title' + ' '*(self.max_column_width-len('title')) +'|Description' + ' '*(self.max_column_width-len('description')) + '|Is Done' + '|Start Date' + '|End Date  ' + '|Assignees' + '|`\n'
            else:
                content+=task_text
        if pages[len(pages)-1] != content:
            pages.append(content)
        return pages

    def _build(self, page, overwrite):
        self.view = discord.ui.View()
        self.page_index = page
        self.previous_button.disabled = False
        self.next_button.disabled = False
        if page == 0:
            self.previous_button.disabled = True
        if page == len(self.pages)-1:
            self.next_button.disabled = True
        if self.pages == [] or overwrite:
            self.pages = self._gen_pages(self.tasks)
        self.view.add_item(self.previous_button)
        self.view.add_item(self.next_button)
        content = self.pages[page]
        return Message.Content(content=content, view=self.view)

    def send(self, tasks, page=0, overwrite=False, delete_last = True):
        self.tasks = tasks
        return self._send(self._build(page, overwrite), delete_last)
    
    async def next_button_callback(self, interaction):
        self.send(self.tasks, self.page_index+1)

    async def previous_button_callback(self, interaction):
        self.send(self.tasks, self.page_index-1)

class TaskSelectMessage(Message):
    #max values: https://discordpy.readthedocs.io/en/stable/interactions/api.html?highlight=select#discord.ui.Select
    def __init__(self, loop, channel=None, max_values = 25):
        super().__init__(loop, channel)
        self.view = discord.ui.View()
        self.max_values = max_values
        self.task_selector_select = discord.ui.Select(max_values=max_values)
        self.cancel_button = discord.ui.Button(label='Cancel')
    
    def _build(self, items):
        #items must be a list with pairs of (label, value)
        self.view = discord.ui.View()
        self.task_selector_select.max_values = len(items) if len(items) < self.max_values else self.max_values
        self.task_selector_select.options = [discord.SelectOption(label = label, value=value) for label,value in (items)]
        self.view.add_item(self.task_selector_select)
        self.view.add_item(self.cancel_button)
        return Message.Content(view = self.view)

    def send(self, items): 
        self._send(self._build(items))

class NotificationMessage(Message):
    def __init__(self, loop, channel=None):
        super().__init__(loop, channel)

    def _build(self, task):
        assignees = []
        for i in task.get_assignees():
            data = i.split(":")
            assignees.append(f'{data[1]}') if data[0] == 'Role' else assignees.append(f'<@{data[1]}>')
        end_date = f'before {task.get_end_date().strftime("%d/%m/%Y")}' if task.get_end_date() is not None else ''
        content = f'# TASK {task.get_title()} is not done\n## finish this task {end_date}\n{task.get_description()}\n{' '.join(assignees)}'
        return Message.Content(content = content)

    def send(self, task):
        self._send(self._build(task))

class TimeMeasure():
    SECOND = 1
    MINUTE = 60
    HOUR = MINUTE*60
    DAY = HOUR*24

class Notification():
    def __init__(self, rate, measure, task, start_date) -> None:
        self.rate = rate
        self.measure = measure
        self.task = task
        self.start_date = start_date

    async def _run(self, loop, channel):
        while True:
            await asyncio.sleep(self.rate*self.measure)
            if not self.task.is_done():
                message = NotificationMessage(loop, channel)
                message.send(self.task)
                self.on_notify()

    def run(self, loop, channel):
        asyncio.run_coroutine_threadsafe(self._run(loop, channel), loop=loop).add_done_callback(self.on_notification_end)
    
    def on_notify(self):
        pass
    
    def on_notification_end(self, future):
        pass

class Task():
    def __init__(self) -> None:
        self.title:str
        self.assignees:str
        self.description:str
        self.done:bool = False
        self.start_date=datetime.datetime.today()
        self.end_date=None
        self.notification:Notification|None = None
        self.trello_id = None

    def format_if_date(self, value):
        try:
            return datetime.datetime.strptime(value, '%d/%m/%Y')
        except Exception as e:
            print(e)
            return value

    def update(self, **kwargs):
        for k,v in kwargs.items():
            if k == 'id':
                k = 'trello_id'
            v = self.format_if_date(v)
            setattr(self, k, v)

    def get_title(self):
        return self.title

    def get_assignees(self):
        if hasattr(self, 'assignees'):
            return self.assignees
        else: return []
    
    def get_description(self):
        return self.description

    def get_start_date(self):
        return self.start_date

    def get_end_date(self):
        return self.end_date

    def set_done(self, done):
        self.done = done

    def is_done(self):
        return self.done

    def set_title(self, title):
        self.title = title

    def set_assignees(self, assignees):
        self.assignees = assignees
    
    def set_content(self, description):
        self.description = description

    def set_start_date(self, start_date:str|datetime.datetime):
        if isinstance(start_date, str):
            self.start_date = datetime.datetime.strptime(start_date, '%d/%m/%Y')
        else:
            self.start_date = start_date

    def set_end_date(self, end_date:str|datetime.datetime):
        if isinstance(end_date, str):
            try:
                self.end_date = datetime.datetime.strptime(end_date, '%d/%m/%Y')
            except:
                self.end_date = self.end_date
        else:
            self.end_date = end_date

    def set_notification(self, notification:Notification|None):
        self.notification = notification

    def get_notification(self):
        return self.notification

    def get_trello_id(self):
        return self.trello_id

class EditTaskMessage(Message):
    def __init__(self, loop, channel=None):
        super().__init__(loop, channel)
        self.create_button = discord.ui.Button(label='Create', style = discord.ButtonStyle.primary)
        self.edit_button = discord.ui.Button(label='Edit', style = discord.ButtonStyle.primary)
        self.delete_button = discord.ui.Button(label='Delete', style=discord.ButtonStyle.danger)
        self.cancel_button = discord.ui.Button(label='Cancel')
    
    def _build(self, task:Task|None):
        self.view = discord.ui.View(timeout = None)
        self.view.add_item(self.create_button)
        self.view.add_item(self.edit_button)
        self.view.add_item(self.delete_button)
        self.view.add_item(self.cancel_button)
        return Message.Content(view = self.view)

    def send(self, task:Task|None = None, delete_last=True):
        self._send(self._build(task), delete_last)

class ConfirmMessage(Message):
    def __init__(self, loop, channel=None):
        super().__init__(loop, channel)
        self.confirm_button = discord.ui.Button(label='Confirm', style=discord.ButtonStyle.primary)
        self.cancel_button = discord.ui.Button(label='Cancel')

    def _build(self, title, description):
        self.view = discord.ui.View(timeout = None)
        self.view.add_item(self.confirm_button)
        self.view.add_item(self.cancel_button)
        content = f'# {title}\n{description}'
        return Message.Content(content=content, view = self.view)

    def send(self, title, description = '', delete_last = False):
        self._send(self._build(title, description), delete_last)

class TaskManager():
    def __init__(self, loop, guild_id, notification_channel, trello:trello.Trello|None, persist_dir = 'tasks') -> None:
        self.tasks = []
        self.loop = loop
        self.guild_id = guild_id
        self.trello = trello
        self.notification_channel = notification_channel
        self.persist_dir = persist_dir if persist_dir[-1] != '/' else persist_dir[:len(persist_dir)-1]
        try:
            os.makedirs(self.persist_dir)
        except:
            pass
        if f'{self.guild_id}.tasks' in os.listdir(self.persist_dir):
            with open(f'{self.persist_dir}/{self.guild_id}.tasks', 'rb') as file:
                self.tasks = pickle.load(file)
        for i in self.tasks:
            notification = i.get_notification()
            if notification is not None:
                notification.run(self.loop, self.notification_channel)
    
    def set_trello(self, trello:trello.Trello|None):
        self.trello = trello

    def sync_local(self):
        if self.trello is not None:
            self.trello.sync()
            tasks = self.trello.get_tasks()
            ids = [i.get_trello_id() for i in self.tasks]
            for task in tasks:
                if not task.get_id() in ids:
                    t = Task()
                    t.update(**vars(task))
                    self.tasks.append(t)
                else:
                    self.tasks[ids.index(task.get_id())].update(**vars(task))
        self.persist_tasks()


    def sync_trello(self):
        if self.trello is not None:
            self.trello.sync()
            tasks = self.trello.get_tasks()
            ids = [i.get_trello_id() for i in self.tasks]
            for task in tasks:
                if task.get_id() in ids:
                    task.update(**vars(self.tasks[ids.index(task.get_trello_id())]))
                    self.trello.update_task(task)

    def create_task(self, ctx, assignees):
        assignees = [i.__class__.__name__+':'+str(i.name if isinstance(i, discord.Role) else i.id) for i in assignees] if len(assignees)>0 else ['User:'+str(ctx.author.id),]
        edit_message = EditTaskMessage(self.loop, ctx.channel)
        edit_message.bind_button(('create', 'edit', 'delete', 'cancel'), (self.create_button_callback, self.edit_button_callback, self.delete_button_callback, self.cancel_button_callback))
        edit_message.set_extra(assignees = assignees)
        edit_message.send()

    def assign_task(self, ctx, assignees):
        assignees = [i.__class__.__name__+':'+str(i.name if isinstance(i, discord.Role) else i.id) for i in assignees] if len(assignees)>0 else ['User:'+str(ctx.author.id),]
        self.send_select_message(ctx.channel, [(v.get_title(),k) for k,v in enumerate(self.tasks)], self.assign_task_callback, assignees=assignees)

    def unassign_task(self, ctx, assignees):
        assignees = [i.__class__.__name__+':'+str(i.name if isinstance(i, discord.Role) else i.id) for i in assignees] if len(assignees)>0 else ['User:'+str(ctx.author.id),]
        self.send_select_message(ctx.channel, [(v.get_title(),k) for k,v in enumerate(self.tasks)], self.unassign_task_callback, assignees=assignees)

    def list_tasks(self, ctx):
        task_list_message = TaskListMessage(self.loop, ctx.channel)
        task_list_message.send(self.tasks)

    def set_done(self, ctx, is_done):
        tasks = [(v.get_title(), k) for k,v in enumerate(self.tasks) if not v.is_done() == is_done]
        self.send_select_message(ctx.channel, tasks, self.set_done_callback, is_done = is_done)

    def persist_tasks(self):
        with open(f'{self.persist_dir}/{self.guild_id}.tasks', 'bw') as file:
            pickle.dump(self.tasks, file)

    def delete_task(self, id):
        self.tasks.pop(id)

    def create_notification(self, ctx, rate, measure):
        self.send_select_message(ctx.channel, [(v.get_title(),k) for k,v in enumerate(self.tasks)], self.create_notification_callback, rate = rate, measure = measure)

    def set_start_date(self, ctx, date):
        self.send_select_message(ctx.channel, [(v.get_title(),k) for k,v in enumerate(self.tasks)], self.set_start_date_callback, date=date)

    def set_end_date(self, ctx, date):
        self.send_select_message(ctx.channel, [(v.get_title(),k) for k,v in enumerate(self.tasks)], self.set_end_date_callback, date=date)

    async def create_button_callback(self, interaction):
        await interaction.message.delete()
        modal = TaskModal(title='CREATE TASK')
        modal.set_extra(assignees = interaction.extras['assignees'])
        modal.set_submit_callback(self.create_modal_callback)
        await interaction.response.send_modal(modal)
        return

    async def edit_button_callback(self, interaction):
        await interaction.message.delete()
        self.send_select_message(interaction.channel, [(v.get_title(),k) for k,v in enumerate(self.tasks)], self.task_select_edit_callback, 1)
        return

    async def delete_button_callback(self, interaction):
        await interaction.message.delete()
        self.send_select_message(interaction.channel, [(v.get_title(),k) for k,v in enumerate(self.tasks)], self.task_select_delete_callback)
        return

    def send_select_message(self, channel, items, callback, max_values=25, **extra):
        task_select_message = TaskSelectMessage(self.loop, channel, max_values)
        task_select_message.bind_button(('task_selector'), (callback), '_select')
        task_select_message.bind_button(('cancel'), (self.cancel_button_callback))
        task_select_message.set_extra(**extra)
        task_select_message.send(items)

    async def create_modal_callback(self, interaction):
        t = Task()
        t = self._modal_data_insert(interaction, t)
        self.tasks.append(t)
        self.persist_tasks()
        await interaction.response.defer()
        return

    async def edit_modal_callback(self, interaction):
        self._modal_data_insert(interaction, interaction.extras['task'])
        self.persist_tasks()
        await interaction.response.defer()
        return

    def _modal_data_insert(self, interaction, task):
        kwargs = {}
        for i in interaction.data.get('components', []):
            for j in i.get('components', []):
                kwargs[j.get('custom_id')] = j.get('value', '').strip()
                if j.get('custom_id') == 'start_date' and j.get('value', '').strip() == '':
                    today = datetime.date.today()
                    kwargs[j.get('custom_id')] = datetime.datetime(year=today.year, month=today.month, day=today.day)
                if j.get('custom_id') == 'end_date' and j.get('value', '').strip() == '':
                    kwargs[j.get('custom_id')] = None
        kwargs.update(interaction.extras)
        task.update(**kwargs)
        return task

    async def cancel_button_callback(self, interaction):
        await interaction.message.delete()

    async def task_select_edit_callback(self, interaction):
        await interaction.message.delete()
        task = self.tasks[int(interaction.data['values'][0])]
        data = vars(task).copy()
        modal = TaskModal(title='EDIT TASK')
        modal_ids = modal.get_items_id()
        for k in list(data.keys()).copy():
            if k not in modal_ids:
                data.pop(k)
        modal.set_data(**data)
        modal.set_submit_callback(self.edit_modal_callback)
        modal.set_extra(task = task)
        await interaction.response.send_modal(modal)

    async def task_select_delete_callback(self, interaction):
        await interaction.message.delete()
        task = interaction.data['values']
        confirm = ConfirmMessage(self.loop, interaction.channel)
        confirm.bind_button('confirm', self.delete_confirm_callback)
        confirm.set_extra(task = task)
        confirm.send('DELETE TASK?', f'task "{self.tasks[task[0]].title}" will be deleted') if len(task) == 1 else confirm.send('DELETE TASKS?', 'Multiple tasks will be deleted') 

    async def delete_confirm_callback(self, interaction):
        await interaction.message.delete()
        tasks = [int(i) for i in interaction.extras['task']]
        tasks = sorted(tasks, reverse=True)
        for task in tasks:
            self.delete_task(task)
        self.persist_tasks()

    async def set_done_callback(self, interaction):
        await interaction.message.delete()
        for i in interaction.data['values']:
            task = self.tasks[int(i)]
            task.set_done(interaction.extras['is_done'])
        self.persist_tasks()

    async def create_notification_callback(self, interaction):
        await interaction.message.delete()
        for i in interaction.data['values']:
            task = self.tasks[int(i)]
            notification = Notification(interaction.extras['rate'], getattr(TimeMeasure, interaction.extras['measure']), task, None)
            task.set_notification(notification)
            notification.run(self.loop, self.notification_channel)
        self.persist_tasks()

    async def assign_task_callback(self, interaction):
        await interaction.message.delete()
        for i in interaction.data['values']:
            task = self.tasks[int(i)]
            assignees = task.get_assignees()
            for assignee in interaction.extras.get('assignees', []):
                if assignee not in assignees:
                    assignees.append(assignee)
            task.set_assignees(assignees)
        self.persist_tasks()
                                         
    async def unassign_task_callback(self, interaction):
        await interaction.message.delete()
        for i in interaction.data['values']:
            task = self.tasks[int(i)]
            assignees = task.get_assignees()
            for assignee in interaction.extras.get('assignees', []):
                if assignee in assignees:
                    assignees.pop(assignees.index(assignee))
            task.set_assignees(assignees)
        self.persist_tasks()

    # Can rewrite in 1 function
    async def set_start_date_callback(self, interaction):
        await interaction.message.delete()
        for i in interaction.data['values']:
            task = self.tasks[int(i)]
            task.set_start_date(interaction.extras['date'])
        self.persist_tasks()

    async def set_end_date_callback(self, interaction):
        await interaction.message.delete()
        for i in interaction.data['values']:
            task = self.tasks[int(i)]
            task.set_end_date(interaction.extras['date'])
        self.persist_tasks()

class Tag():
    
    def __init__(self) -> None:
        self.name:str
        self.users:str

    def get_users(self):
        return self.users

    def get_name(self):
        return self.name

    def has_user(self, user):
        return user in self.users
