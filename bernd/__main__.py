import argparse
import configparser
import importlib

from matrix_bot_api.matrix_bot_api import MatrixBotAPI
from pathlib import Path

def main():

    # Interpret command line arguments
    cmd = argparse.ArgumentParser()
    cmd.add_argument("-c", "--config", default="/etc/prism/config.py")
    args = cmd.parse_args()

    # Read the configuration file
    config = configparser.ConfigParser()
    config.sections()
    config.read(args.config)

    username = config['BotMatrixId']['USERNAME']
    password = config['BotMatrixId']['PASSWORD']
    server = config['BotMatrixId']['SERVER']
    rooms = config['BotMatrixId']['ROOMS'].split(';')

    print("Bernd steht langsam auf...")

    # Create an instance of the MatrixBotAPI
    # The room argument is provided with empty list, as the original bot API
    # doesn't support string arguments but room objects, which we can't create
    # without an existing bot object. We add our room later. This argument also
    # prevents the bot from accepting random room invites.
    bot = MatrixBotAPI(username, password, server, [])

    # With an established connection and existing bot object, we tell the bot
    # manually to join or specified rooms
    for roomid in rooms:
        print("Trying to join room {}".format(roomid))
        try:
            bot.handle_invite(roomid, None)
        except matrix_client.errors.MatrixRequestError:
            print("Failed to join room {}".format(roomid))

    # Import all defined plugins
    plugin_path = Path(__file__).resolve().parent.parent / "plugins"
    print("Loading plugins from: {}".format(plugin_path))

    help_desc = []

    for filename in plugin_path.glob("*.py"):
        if (plugin_path / filename).exists():

            modname = 'plugins.%s' % filename.stem
            loader = importlib.machinery.SourceFileLoader(
                modname, str(filename))

            module = loader.load_module(modname)
            help_desc.append(module.HELP_DESC)  # collect plugin help texts

            # skip help module, collect all help texts before registering
            if (modname == 'plugins.help'):
                help_module = module
                help_modname = modname
            else:
                module.register_to(bot)
                print("  [+] {} loaded".format(modname))

    # Build the help message from the collected plugin description fragments
    help_desc.sort(reverse=True)

    line = ''
    for i in range(80):
        line += '-'
    help_desc.insert(0, line)

    help_desc.insert(0, '\nBernd Lauert Commands and Capabilities')
    help_txt = "\n".join(help_desc)

    with open('help_text', 'w') as f:
        f.write(help_txt)

    # load the help module after all help texts have been collected
    help_module.register_to(bot)
    print("  [+] {} loaded".format(help_modname))

    # Start polling
    bot.start_polling()

    print("Bernd Lauert nun.")

    # Infinitely read stdin to stall main thread while bot runs in other threads
    while True:
        try:
            w = input("press q+<enter> or ctrl+d to quit\n")
            if (w == 'q'):
                return 0
        except EOFError:
            return 0


if __name__ == "__main__":
    main()
