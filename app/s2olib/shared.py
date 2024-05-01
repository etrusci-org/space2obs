import argparse
import datetime
import importlib
import itertools
import json
import os
import pathlib
import sys
import time

if os.name == 'nt':
    import msvcrt
    import ctypes

    class _CursorInfo(ctypes.Structure):
        _fields_ = [
            ('size', ctypes.c_int),
            ('visible', ctypes.c_byte),
        ]

import requests # https://github.com/psf/requests


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


ENABLED_TOOLS: list[str] = [
    'apod',
    'dnmap',
    'eonet',
    'soho',
]

DEFAULT_CACHE_DIR: pathlib.Path = pathlib.Path(__file__).parents[1].resolve() / 'cache'
DEFAULT_SECRETS_FILE: pathlib.Path = pathlib.Path(__file__).parents[1].resolve() / 'secrets.json'
DEFAULT_INTERVAL: int = 300
DEFAULT_RETRY_DELAY: int = 60
DEFAULT_REQUEST_TIMEOUT: int = 10

ARGPARSER_SETUP: dict[str, any] = {
    'description': 'For more help and examples see README.md or https://github.com/etrusci-org/space2obs',
    'allow_abbrev': False,
    'add_help': False,
}

ARG_HELP: dict[str, any] = {
    'name_or_flags': ['-h', '--help'],
    'action': 'help',
    'help': 'Display this help message and exit.',
}
ARG_TOOL: dict[str, any] = {
    'name_or_flags': ['tool'],
    'metavar': 'TOOL',
    'type': str,
    'choices': ENABLED_TOOLS,
    'help': f'Specify the tool to execute. Choices: {", ".join(ENABLED_TOOLS)}',
}
ARG_CACHE_DIR: dict[str, any] = {
    'name_or_flags': ['-c', '--cache-dir'],
    'metavar': 'PATH',
    'type': pathlib.Path,
    'default': DEFAULT_CACHE_DIR,
    'help': f'Specify the directory path where cache files will be stored. Default: {DEFAULT_CACHE_DIR}',
}
ARG_SECRETS_FILE: dict[str, any] = {
    'name_or_flags': ['-s', '--secrets-file'],
    'metavar': 'PATH',
    'type': pathlib.Path,
    'default': DEFAULT_SECRETS_FILE,
    'help': f'Specify the file path where secrets are stored. Default: {DEFAULT_SECRETS_FILE}',
}
ARG_INTERVAL: dict[str, any] = {
    'name_or_flags': ['-i', '--interval'],
    'metavar': 'SEC',
    'type': int,
    'default': DEFAULT_INTERVAL,
    'help': f'Set the interval in seconds for the tool to check for new remote data. Default: {DEFAULT_INTERVAL}',
}
ARG_RETRY_DELAY: dict[str, any] = {
    'name_or_flags': ['-r', '--retry-delay'],
    'metavar': 'SEC',
    'type': int,
    'default': DEFAULT_RETRY_DELAY,
    'help': f'Set the delay in seconds before retrying if the situation requires it. Default: {DEFAULT_RETRY_DELAY}',
}
ARG_REQUEST_TIMEOUT: dict[str, any] = {
    'name_or_flags': ['-t', '--request-timeout'],
    'metavar': 'SEC',
    'type': int,
    'default': DEFAULT_REQUEST_TIMEOUT,
    'help': f'Set the maximum time in seconds for a remote request to complete. Default: {DEFAULT_REQUEST_TIMEOUT}',
}

ARGS: list[dict[str, any]] = [
    ARG_HELP,
    ARG_CACHE_DIR,
    ARG_SECRETS_FILE,
    ARG_INTERVAL,
    ARG_RETRY_DELAY,
    ARG_REQUEST_TIMEOUT,
]

SPINNER_FRAMES: dict[str, dict[str, float | list[str]]] = {
    'spinright': {
        'i': 0.5,
        'f': [
            '|',
            '/',
            '-',
            '\\',
        ],
    },
    'spinleft': {
        'i': 0.5,
        'f': [
            '\\',
            '-',
            '/',
            '|',
        ],
    },
}


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


ARG_GROUPS: list[tuple[str, list[dict[str, any]]]] = [
    ('shared options', ARGS),
]

for d in ENABLED_TOOLS:
    m = importlib.import_module(f's2olib.{d}')
    ARG_GROUPS.append((f'{d} options', getattr(m, 'ARGS')))


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


def add_args(dest: argparse.ArgumentParser | argparse._ArgumentGroup, args: list[dict[str, any]]) -> None:
    for arg in args:
        name_or_flags: list = arg['name_or_flags']
        del arg['name_or_flags']
        dest.add_argument(*name_or_flags, **arg)


def get_secrets(file: pathlib.Path, keys: list[str]) -> dict[str, str]:
    try:
        dump: dict[str, str] = json.loads(file.read_text())
        secrets: dict[str, str | None] = {}

        for k in keys:
            secrets[k] = dump.get(k, None)

        return secrets

    except json.decoder.JSONDecodeError as e:
        msg(f'failed to parse secrets file: {e}')
        exit(1)


def msg(msg: str = '', start: str = '', end: str = '\n', plain: bool = False) -> None:
    if msg:
        if not plain:
            sys.stdout.write(f'{start}{datetime.datetime.now().strftime("%H:%M:%S")} | {msg}{end}')
        else:
            sys.stdout.write(f'{start}{msg}{end}')
    else:
        sys.stdout.write(f'{start}{end}')

    sys.stdout.flush()


def endofloop_idle(interval: int) -> None:
    msg(f'next run at {next_datetime(interval)}', end=' ')
    spinner(interval, end='\n\n')


def retry_idle(retry_delay: int) -> None:
    msg(f'retry at {next_datetime(retry_delay)}', end=' ')
    spinner(retry_delay, 'spinleft', end='\n\n')


def next_datetime(in_sec: int = 0, format: str = '%H:%M:%S') -> str:
    return datetime.datetime.fromtimestamp(time.time() + in_sec).strftime(format)


def fetch_remote_data(url: str, timeout: int, content_types: list[str]) -> requests.Response | None:
    try:
        res = requests.get(url, timeout=timeout)
        res.raise_for_status()

        res_content_type: list[str] = res.headers['content-type'].lower().split(';')
        # print(res.headers)
        # print(res_content_type)

        if not res:
            return None

        for v in res_content_type:
            v = v.strip()
            if v in content_types:
                msg(f'retrieved {bytes_for_humans(len(res.content))}')
                return res

        return None

    except Exception as e:
        msg(f'request error: {e}')


def bytes_for_humans(bytes: int, unit: str = 'kb', prec: int = 1) -> float:
    unit = unit.lower()
    factor: int = 10
    if unit == 'mb': factor = 20
    if unit == 'gb': factor = 30
    if unit == 'tb': factor = 40
    if unit == 'pb': factor = 50
    return f'{bytes / float(1<<factor):.{prec}f} {unit.upper()}'


def check_xrate(res: requests.Response) -> None:
    xrate_rem = int(res.headers.get('x-ratelimit-remaining', -1))
    xrate_limit = int(res.headers.get('x-ratelimit-limit', -1))

    msg(f'rate limit usage {xrate_rem}/{xrate_limit}')

    if xrate_rem <= 0:
        msg(f'rate limit exceeded')
        exit(10)


def spinner(duration: float, type: str = 'spinright', start: str = '', end: str = '') -> None:
    if start != '':
        sys.stdout.write(start)
        sys.stdout.flush()

    until: float = time.time() + duration
    frames = itertools.cycle(SPINNER_FRAMES[type]['f'])

    while time.time() < until:
        f = next(frames)
        sys.stdout.write(f)
        sys.stdout.flush()
        time.sleep(SPINNER_FRAMES[type]['i'])
        sys.stdout.write('\b' * len(f))

    sys.stdout.write(' ' * len(f) + '\b' * len(f))

    if end:
        sys.stdout.write(end)

    sys.stdout.flush()


def disable_terminal_cursor() -> None:
    if os.name == 'posix':
        sys.stdout.write('\033[?25l')
        sys.stdout.flush()

    if os.name == 'nt':
        ci = _CursorInfo()
        handle = ctypes.windll.kernel32.GetStdHandle(-11)
        ctypes.windll.kernel32.GetConsoleCursorInfo(handle, ctypes.byref(ci))
        ci.visible = False
        ctypes.windll.kernel32.SetConsoleCursorInfo(handle, ctypes.byref(ci))


def enable_terminal_cursor() -> None:
    if os.name == 'posix':
        sys.stdout.write('\033[?25h')
        sys.stdout.flush()

    if os.name == 'nt':
        ci = _CursorInfo()
        handle = ctypes.windll.kernel32.GetStdHandle(-11)
        ctypes.windll.kernel32.GetConsoleCursorInfo(handle, ctypes.byref(ci))
        ci.visible = True
        ctypes.windll.kernel32.SetConsoleCursorInfo(handle, ctypes.byref(ci))


def megastrip(text: str) -> str:
    return ' '.join(text.split())
