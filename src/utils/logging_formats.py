import logging

def get_logging_formatter(with_colors: bool):
    "Return a logging formatter with or without colors"
    if not with_colors:
        return logging.Formatter(
            fmt="[{asctime}] {levelname:<7} [{name}] {message}",
            datefmt="%Y-%m-%d %H:%M:%S", style='{'
        )

    return _ColourFormatter()

class _ColourFormatter(logging.Formatter):
    "A formatter that adds colors to the log messages"
    LEVEL_COLOURS = [
        (logging.DEBUG, '\x1b[40;1m'),
        (logging.INFO, '\x1b[34;1m'),
        (logging.WARNING, '\x1b[33;1m'),
        (logging.ERROR, '\x1b[31m'),
        (logging.CRITICAL, '\x1b[41m'),
    ]

    FORMATS = {
        level: logging.Formatter(
            f'\x1b[30;1m%(asctime)s\x1b[0m {colour}%(levelname)-7s\x1b[0m \x1b[35m[%(name)s]\x1b[0m %(message)s',
            '%Y-%m-%d %H:%M:%S',
        )
        for level, colour in LEVEL_COLOURS
    }

    def format(self, record):
        formatter = self.FORMATS.get(record.levelno)
        if formatter is None:
            formatter = self.FORMATS[logging.DEBUG]

        # Override the traceback to always print in red
        if record.exc_info:
            text = formatter.formatException(record.exc_info)
            record.exc_text = f'\x1b[31m{text}\x1b[0m'

        output = formatter.format(record)

        # Remove the cache layer
        record.exc_text = None
        return output
