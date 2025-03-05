import requests
import json
class TrelloTask():
    def __init__(self, title:str = '', description:str='', id:str='', done:bool=False) -> None:
        self.title = title
        self.description = description
        self.id = id
        self.done = done

    def set_title(self, title):
        self.title = title
        
    def set_description(self, description):
        self.description = description

    def set_done(self, done):
        self.done = done

    def get_title(self):
        return self.title

    def get_description(self):
        return self.description

    def get_id(self):
        return self.id

    def is_done(self):
        return self.done

    def update(self, **kwargs):
        for k,v in kwargs.items():
            if hasattr(self, k) and k != 'id':
                setattr(self, k, v)

    def get_trello_kwargs(self):
        kwargs = {
            'name' : self.title,
            'desc' : self.description,
            'dueComplete' : str(self.done).lower()
        }
        return kwargs
class Trello():
    def __init__(self, api_key, token, board_id, *args, **kwargs) -> None:
        self.api_key = api_key
        self.token = token
        self.board_id = board_id
        self.base_url = 'https://api.trello.com/1/'
        self.tasks = []
        print(vars(self))
    
    def sync(self):
        url = f'{self.base_url}/boards/{self.board_id}/cards'
        data = self.request_json('GET', url)
        self.tasks = []
        for card in data:
            self.tasks.append(TrelloTask(card.get('name'), card.get('desc'), card.get('id'), card.get('badges').get('dueComplete')))
        
    def request_json(self, method, url, **kwargs):
        query = {'key': self.api_key, 'token': self.token}
        query.update(kwargs)
        response = requests.request(method, url, params=query)
        return response.json()

    def get_tasks(self):
        return self.tasks

    def update_task(self, task:TrelloTask):
        url = f'{self.base_url}/cards/{task.get_id()}'
        self.request_json('PUT', url, **task.get_trello_kwargs())



def main():
    cfg = json.loads(open('./cfg.json', 'r').read())
    t = Trello(cfg.get('trello_api_key'), cfg.get('trello_token'), 'w2ViRfAv')
    t.sync()

    for i in t.get_tasks():
        print(vars(i))
    #print(t.get_tasks())
if __name__ == "__main__":
    main()
