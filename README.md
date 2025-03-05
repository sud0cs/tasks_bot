# Tasks
a discord bot to manage tasks, with trello "support"

# Features
- poorly written code
- a lot of bugs
- trello support??

# TODO
- allow bulk selection of tasks
- fix task_list message (it sucks)
- fix other bugs
- fix notification message
- add comments and refactor code
- fix more bugs
- add more trello options

# Commands
| command | arguments | description |
|-|-|-|
| task | mentions to users or roles (optional, default is command author) | shows a menu to create, edit or delete tasks |
| list_tasks | - | sends a message listing all tasks |
| assign | mentions to users or roles (optional, default is command author) | assigns mentioned users to a task |
| unassign | mentions to users or roles (optional, default is command author) | unassigns mentioned users from a task |
| set_done | - | marks a task as done |
| set_undone | - | marks a task as undone |
| notify_every | int count, string time_measure | sends a reminder to finish the task. Example: !notify_every 10 minutes |
| assign_trello | int board_id | assigns a trello board to the discord server |
| sync_local | - | updates the trello tasks in the bot |
| sync_trello | - | updates the trello tasks in the trello board |
