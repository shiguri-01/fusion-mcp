# Here you define the commands that will be added to your add-in.

# Import the modules corresponding to the commands you created.
# If you want to add an additional command, duplicate one of the existing directories and import it here.
# You need to use aliases (import "entry" as "my_module") assuming you have the default module named "entry".
from .server import entry as server_entry

# Add your imported modules to this list.
# Fusion will automatically call the start() and stop() functions.
commands = [server_entry]


# Assumes you defined a "start" function in each of your modules.
# The start function will be run when the add-in is started.
def start() -> None:
    for command in commands:
        command.start()


# Assumes you defined a "stop" function in each of your modules.
# The stop function will be run when the add-in is stopped.
def stop() -> None:
    for command in commands:
        command.stop()
