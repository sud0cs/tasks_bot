import bot
import asyncio
import json
asyncio.new_event_loop()
if __name__ == "__main__":
    cfg = json.loads(open('./cfg.json', 'r').read())
    _bot = bot.Bot(**cfg)
    try:
        _bot.start()
    except (Exception, KeyboardInterrupt) as e:
        print(e)
