import colorlog


def get_formatter(is_test: bool = False):
    if is_test:
        log_colors = {k: 'bold_purple' for k in ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')}
    else:
        log_colors = {
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'bold_red',
        }

    return colorlog.ColoredFormatter(
        '%(log_color)s%(asctime)s [%(levelname)s] - %(message)s',
        log_colors=log_colors,
    )
