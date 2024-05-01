import argparse
import pathlib
import re

import s2olib.shared


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


API_URL_TPL: str = 'https://eonet.gsfc.nasa.gov/api/v3/events?status={status}&limit={limit}'

STATUS_CHOICES: list[str] = ['all', 'open', 'closed']

DEFAULT_STATUS: str = 'all'
DEFAULT_LIMIT: int = 50
DEFAULT_TEXT_TPL: str = '{status:>6}  {date}  {id}  {categories}:  {title}' # this is a line of the output list, escape \n here in the template... e.g. \n -> \\n

TEXT_TPL_VARS: list[str] = re.findall('({[a-z]+})', DEFAULT_TEXT_TPL)

ENTRY_FUNC: str = 'daemon'

ARGS: list[dict[str, any]] = [
    {
        'name_or_flags': ['--eonet-status'],
        'metavar': 'TYPE',
        'type': str,
        'choices': STATUS_CHOICES,
        'default': DEFAULT_STATUS,
        'help': f'The type of entry to fetch. Choices: {", ".join(STATUS_CHOICES)}. Default: {DEFAULT_STATUS}',
    },
    {
        'name_or_flags': ['--eonet-limit'],
        'metavar': 'NUM',
        'type': int,
        'default': DEFAULT_LIMIT,
        'help': f'Set the maximum number of events to fetch. Default: {DEFAULT_LIMIT}',
    },
    {
        'name_or_flags': ['--eonet-text-template'],
        'metavar': 'TEXT',
        'type': str,
        'default': DEFAULT_TEXT_TPL,
        'help': f'Specify the template of a line in the text file. Add linebreaks with "\\n". Variables: {", ".join(TEXT_TPL_VARS)}. Default: {DEFAULT_TEXT_TPL}'
    },
]


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


def daemon(args: argparse.Namespace):
    api_url = API_URL_TPL.format(status=args.eonet_status, limit=args.eonet_limit)
    obs_data_file: pathlib.Path = args.cache_dir / 'eonet_last_data'
    obs_text_file: pathlib.Path = args.cache_dir / 'eonet_last_text'
    last_content_size: int = obs_data_file.stat().st_size if obs_data_file.is_file() else 0

    while True:
        s2olib.shared.msg(f'downloading events')
        res = s2olib.shared.fetch_remote_data(api_url, args.request_timeout, ['application/json'])

        if not res:
            s2olib.shared.msg('invalid response data')
            s2olib.shared.retry_idle(args.retry_delay)
            continue

        s2olib.shared.check_xrate(res)

        data: dict[str, any] = res.json()

        if len(res.content) == last_content_size:
            s2olib.shared.msg('no change')
        else:
            s2olib.shared.msg(f'updating {obs_data_file.name}')
            obs_data_file.write_bytes(res.content)
            last_content_size = len(res.content)

            text_list: list[str] = []

            for event in data['events']:
                text_list.append(args.eonet_text_template.replace('\\n', '\n').format(
                    id=event['id'],
                    date=event['geometry'][0]['date'].split('T')[0] if not event['closed'] else event['closed'].split('T')[0],
                    status='open' if not event['closed'] else 'closed',
                    categories=', '.join([v['title'] for v in event['categories']]),
                    title=event['title'],
                ))

            s2olib.shared.msg(f'updating {obs_text_file.name}')
            obs_text_file.write_text('\n'.join(text_list))

        s2olib.shared.endofloop_idle(args.interval)
