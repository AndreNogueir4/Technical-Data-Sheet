import colorlog

def get_formatter(is_test: bool = False):
    """ Retorna formatter colorido para terminal """
    if is_test:
        log_colors = {
            'DEBUG': 'bold_purple',
            'INFO': 'bold_purple',
            'WARNING': 'bold_purple',
            'ERROR': 'bold_purple',
            'CRITICAL': 'bold_purple',
        }
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
        log_colors=log_colors
    )