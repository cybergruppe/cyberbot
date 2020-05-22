import json
import logging
import asyncio
import random
import string


from pprint import pprint
from collections import defaultdict

from aiohttp import web

from matrixroom import MatrixRoom


HELP_DESC = ("!gitlab\t\t\t-\tGitlab Webhook Manager/Notifier\n")


# Configuration
ADDRESS = "0.0.0.0"
HTTPPORT = 8080
HTTPSPORT = 4430
PREFERHTTPS = True
PATH = "/webhook" # unused

# Change these if you are running bernd behind a reverse proxy or you do some
# port magic
import socket
HTTPURL  = f"http://{socket.getfqdn()}"
if HTTPPORT != 80:
    HTTPURL  += f":{HTTPPORT}"
HTTPSURL = f"https://{socket.getfqdn()}"
if HTTPSPORT != 443:
    HTTPSURL  += f":{HTTPSPORT}"



class WebhookListener:
    """
    The WebhookListener creates a http and https server, listens to gitlab
    webhooks and triggers handler for the webhooks. It should be global and
    shared between multiple plugin instances

    TODO: Add logging to everything
    """

    def __init__(self,
            address="0.0.0.0",
            http_port="80",
            https_port="443"):
        self.tokens = defaultdict(list) # maps a secrettoken on a list of handlers
        self.is_running = False
        self.currenthid = 0 # unique ids for new hooks

        self.address = address
        self.http_port = http_port
        self.https_port = https_port
        

    async def start(self):
        """
        start servers
        """
        if self.is_running:
            return

        async def handle_request(request):
            # TODO: check path
            if request.method != "POST":
                return web.Response(status=404)

            token = request.headers.get("X-Gitlab-Token")
            event = request.headers.get("X-Gitlab-Event")
            if token is None or event is None:
                return web.Response(status=400)

            if token in self.tokens:
                handlers = [handler for (hid,handler) in self.tokens[token]]
                c = await request.content.read()
                try:
                    jsondata = c.decode("utf-8")
                    content = json.loads(jsondata)
                except UnicodeDecodeError:
                    return web.Response(status=400)
                except:
                    return web.Response(status=400)

                await asyncio.gather(
                        *(handler.handle(token, event, content) for handler in handlers))
                return web.Response(text="OK")

        self.server = web.Server(handle_request)
        self.runner = web.ServerRunner(self.server)
        await self.runner.setup()

        self.http_site = web.TCPSite(self.runner, self.address, self.http_port)
        self.https_site = web.TCPSite(self.runner, self.address, self.https_port)
        await self.http_site.start()
        await self.https_site.start()

        self.is_running = True

    async def nexthookid(self):
        self.currenthid += 1
        return self.currenthid


    async def register_hook(self, secrettoken, handler):
        """
        handler has to be a async function and has to have a method
        called 'handle(token, event, content)' where event is
        the gitlab event and content ist the parsed json from the webhook post
        """
        hookid = self.nexthookid()
        self.tokens[secrettoken].append((hookid,handler))
        return hookid

    async def deregister_hook(self, token, hookid):
        # TODO: Race Conditions?
        h = self.tokens[token]
        for i in range(len(h)):
            if h[i][0] == hookid:
                del h[i]
                break


class LocalHookManager:
    """
    A LocalHookManager loads and stores secrettokens and registers them to the
    webhooklistener
    """
    def __init__(self, plugin, whl):
        """
        whl: webhook listener
        """
        self.plugin = plugin
        self.tokens = None
        self.whl = whl

    async def load_tokens(self):
        if "gitlabtokens" in await self.plugin.kvstore_get_keys():
            jsondata = await self.plugin.kvstore_get_value("gitlabtokens")
            try:
                tokenlist = json.loads(jsondata)
            except:
                tokenlist = []
        else:
            tokenlist = []

        if self.tokens is None:
            self.tokens = {}

        for token in tokenlist:
            await self.add_token(token, store=False)

    async def store_tokens(self):
        if self.tokens is not None:
            jsondata = json.dumps(list(self.tokens.values()))
            await self.plugin.kvstore_set_value("gitlabtokens", jsondata)

    async def add_token(self, token, store=True):
        tokenid = await self.whl.register_hook(token, self)
        self.tokens[tokenid] = token
        if store:
            await self.store_tokens()

    async def rem_token(self, tokenid):
        if tokenid in self.tokens:
            self.whl.deregister_hook(tokenid)
            del self.tokens[tokenid]

    async def handle(token, event, content):
        """
        called by WebhookListener when a hook event occurs
        """
        print("Token event received at localhookmanager")
        # TODO




if "webhook_listener" not in globals():
    logging.info("Creating WebhookListener")
    webhook_listener = WebhookListener(address=ADDRESS,
                                       http_port=HTTPPORT,
                                       https_port=HTTPSPORT)
    # has to be started from an async context
    # this happens in the first register_to call




async def register_to(plugin):

    subcommands = """gitlab [subcommand] [option1 option2 ...]
Available subcommands:
    newhook                 - generate secrettoken for a new webhooks
    remhook hooknbr         - remove a webhook subscription
    listhooks               - show subscribed webhooks

How does it work?
    You first create a new secret token for a hook using the 'newhook' command.
    Then open your gitlab repo page and navigate to 'Settings>Webhooks'.
    There, you enter the url and secret token returned by the 'newtoken'
    command and enter all event types you want to get notifications for and
    press 'Add webhook'.

See <a href="https://docs.gitlab.com/ee/user/project/integrations/webhooks.html">here</a> for more information on gitlab webhooks.
"""

    if not webhook_listener.is_running:
        await webhook_listener.start()

    lhm = LocalHookManager(plugin, webhook_listener)
    await lhm.load_tokens()


    def format_help(text):
        html_text = "<pre><code>" + text + "</code></pre>\n"
        return html_text

    async def show_help():
        formatted_subcommands = format_help(subcommands)
        await plugin.send_html(formatted_subcommands, subcommands)


    async def handle_newhook(args):
        chars = string.ascii_letters + string.digits
        n = 16
        token = "".join(random.choice(chars) for i in range(n))
        if PREFERHTTPS:
            url = HTTPSURL + PATH
        else:
            url = HTTPURL + PATH
        await lhm.add_token(token)
        text = f"Successfully created token."
        await plugin.send_text(text)
        html = f"URL: {url}\ntoken: {token}"
        await plugin.send_html(format_help(html))


    async def handle_remhook(args):
        if not args:
            await show_help()
        else:
            await lhm.rem_token(args[0])
            await plugin.send_text("Successfully removed token")
            

    async def handle_listhooks(args):
        html = "\n".join(f"{tokenid:} - " + token[:4] + len(token-4)*"*" \
                for (tokenid,token) in lhm.tokens)
        await plugin.send_html(format_help(html))


    async def gitlab_callback(room, event):
        args = plugin.extract_args(event)
        args.pop(0)
        if len(args) == 0:
            await show_help()
        elif args[0] == "newhook":
            args.pop(0)
            await handle_newhook(args)
        elif args[0] == "remhook":
            args.pop(0)
            await handle_remhook(args)
        elif args[0] == "listhooks":
            args.pop(0)
            await handle_listhooks(args)
        else:
            await show_help()

    gitlab_handler = plugin.CommandHandler("gitlab", gitlab_callback)
    plugin.add_handler(gitlab_handler)
