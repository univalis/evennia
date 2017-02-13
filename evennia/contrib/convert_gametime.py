"""
Convert gametime

Contrib - Griatch 2017

This is the game-dependent part of the evennia.utils.gametime module
that used to be settable from the settings file. Since this was just
a bunch of conversion routines, it is now moved to a contrib since it
is highly unlikely its use is of general game use. The utils.gametime
module deals in seconds, and you can use this contrib to convert
that to fit the calendar of your game.

Usage:
    Import and use as-is or copy this module to mygame/world and
    modify it to your needs there.

"""

# change these to fit your game world

from django.conf import settings
from evennia import DefaultScript
from evennia.utils.create import create_script
from evennia.utils.gametime import gametime
# The game time speedup  / slowdown relative real time
TIMEFACTOR = settings.TIME_FACTOR

# Game-time units, in game time seconds. These are supplied as a
# convenient measure for determining the current in-game time, e.g.
# when defining in-game events. The words month, week and year can  be
# used to mean whatever units of time are used in your game.
SEC = 1
MIN = getattr(settings, "SECS_PER_MIN", 60)
HOUR = getattr(settings, "MINS_PER_HOUR", 60) * MIN
DAY = getattr(settings, "HOURS_PER_DAY", 24) * HOUR
WEEK = getattr(settings, "DAYS_PER_WEEK", 7) * DAY
MONTH = getattr(settings, "WEEKS_PER_MONTH", 4) * WEEK
YEAR = getattr(settings, "MONTHS_PER_YEAR", 12) * MONTH
UNITS = getattr(settings, "TIME_UNITS", {
        "sec": SEC,
        "min": MIN,
        "hr": HOUR,
        "hour": HOUR,
        "day": DAY,
        "week": WEEK,
        "month": MONTH,
        "year": YEAR,
        "yr": YEAR,
})


def time_to_tuple(seconds, *divisors):
    """
    Helper function. Creates a tuple of even dividends given a range
    of divisors.

    Args:
        seconds (int): Number of seconds to format
        *divisors (int): a sequence of numbers of integer dividends. The
            number of seconds will be integer-divided by the first number in
            this sequence, the remainder will be divided with the second and
            so on.
    Returns:
        time (tuple): This tuple has length len(*args)+1, with the
            last element being the last remaining seconds not evenly
            divided by the supplied dividends.

    """
    results = []
    seconds = int(seconds)
    for divisor in divisors:
        results.append(seconds // divisor)
        seconds %= divisor
    results.append(seconds)
    return tuple(results)


def gametime_to_realtime(format=False, **kwargs):
    """
    This method helps to figure out the real-world time it will take until an
    in-game time has passed. E.g. if an event should take place a month later
    in-game, you will be able to find the number of real-world seconds this
    corresponds to (hint: Interval events deal with real life seconds).

    Kwargs:
        format (bool): Formatting the output.
        times (int): The various components of the time (must match UNITS).

    Returns:
        time (float or tuple): The realtime difference or the same
            time split up into time units.

    Example:
         gametime_to_realtime(days=2) -> number of seconds in real life from
                        now after which 2 in-game days will have passed.

    """
    # Dynamically creates the list of units based on kwarg names and UNITs list
    rtime = 0
    for name, value in kwargs.items():
        # Allow plural names (like mins instead of min)
        if name not in UNITS and name.endswith("s"):
            name = name[:-1]

        if name not in UNITS:
            raise ValueError("the unit {} isn't defined as a valid " \
                    "game time unit".format(name))
        rtime += value * UNITS[name]
    rtime /= TIMEFACTOR
    if format:
        return time_to_tuple(rtime, 31536000, 2628000, 604800, 86400, 3600, 60)
    return rtime


def realtime_to_gametime(secs=0, mins=0, hrs=0, days=0, weeks=0,
        months=0, yrs=0, format=False):
    """
    This method calculates how much in-game time a real-world time
    interval would correspond to. This is usually a lot less
    interesting than the other way around.

    Kwargs:
        times (int): The various components of the time.
        format (bool): Formatting the output.

    Returns:
        time (float or tuple): The gametime difference or the same
            time split up into time units.

     Example:
      realtime_to_gametime(days=2) -> number of game-world seconds

    """
    gtime = TIMEFACTOR * (secs + mins * 60 + hrs * 3600 + days * 86400 +
                             weeks * 604800 + months * 2628000 + yrs * 31536000)
    if format:
        units = sorted(set(UNITS.values()), reverse=True)
        # Remove seconds from the tuple
        del units[-1]

        return time_to_tuple(gtime, *units)
    return gtime

def real_seconds_until(**kwargs):
    """
    Return the real seconds until game time.

    If the game time is 5:00, TIME_FACTOR is set to 2 and you ask
    the number of seconds until it's 5:10, then this function should
    return 300 (5 minutes).

    Args:
        times (str: int): the time units.

    Example:
        real_seconds_until(hour-5, min=10)

    Returns:
        The number of real seconds before the given game time is up.

    """
    current = gametime(absolute=True)
    units = sorted(set(UNITS.values()), reverse=True)
    # Remove seconds from the tuple
    del units[-1]
    divisors = list(time_to_tuple(current, *units))

    # For each keyword, add in the unit's
    units.append(1)
    higher_unit = None
    for unit, value in kwargs.items():
        # Get the unit's index
        if unit not in UNITS:
            raise ValueError("unknown unit".format(unit))

        seconds = UNITS[unit]
        index = units.index(seconds)
        divisors[index] = value
        if higher_unit is None or higher_unit > index:
            higher_unit = index

    # Check the projected time
    # Note that it can be already passed (the given time may be in the past)
    projected = 0
    for i, value in enumerate(divisors):
        seconds = units[i]
        projected += value * seconds

    if projected <= current:
        # The time is in the past, increase the higher unit
        if higher_unit:
            divisors[higher_unit - 1] += 1
        else:
            divisors[0] += 1

    # Get the projected time again
    projected = 0
    for i, value in enumerate(divisors):
        seconds = units[i]
        projected += value * seconds

    return (projected - current) / TIMEFACTOR

def schedule(callback, repeat=False, **kwargs):
    """
    Call the callback when the game time is up.

    This function will setup a script that will be called when the
    time corresponds to the game time.  If the game is stopped for
    more than a few seconds, the callback may be called with a slight
    delay.  If `repeat` is set to True, the callback will be called
    again next time the game time matches the given time.  The time
    is given in units as keyword arguments.  For instance:
    >>> schedule(func, min=5) # Will call next hour at :05.
    >>> schedule(func, hour=2, min=30) # Will call the next day at 02:30.

    Args:
        callback (function): the callback function that will be called [1].
        repeat (bool, optional): should the callback be called regularly?
        times (str: int): the time to call the callback.

    [1] The callback must be a top-level function, since the script will
        be persistent.

    Returns:
        The number of real seconds before the callback will be
        executed the first time.

    """
    seconds = real_seconds_until(**kwargs)
    script = create_script("evennia.contrib.convert_gametime.GametimeScript",
            key="GametimeScript", desc="A timegame-sensitive script",
            interval=seconds, start_delay=True,
            repeats=-1 if repeat else 1)
    script.db.callback = callback
    script.db.gametime = kwargs
    return script

# Scripts dealing in gametime (use `schedule`  to create it)
class GametimeScript(DefaultScript):

    """Gametime-sensitive script."""

    def at_script_creation(self):
        """The script is created."""
        self.key = "unknown scr"
        self.interval = 100
        self.start_delay = True
        self.persistent = True

    def at_start(self):
        """The script is started or restarted."""
        if self.db.need_reset:
            self.db.need_reset = False
            self.restart(interval=real_seconds_until(**self.db.gametime))

    def at_repeat(self):
        """Call the callback and reset interval."""
        callback = self.db.callback
        if callback:
            callback()

        seconds = real_seconds_until(**self.db.gametime)
        self.restart(interval=seconds)

    def at_server_reload(self):
        """The server is about to reload.  Put the script in need of reset."""
        self.db.need_reset = True

    def at_server_shutdown(self):
        """The server is about to shutdown.  Put the script in need of reset."""
        self.db.need_reset = True


def dummy():
    from typeclasses.rooms import Room
    for room in Room.objects.all():
        room.msg_contents("The script ticks...")
