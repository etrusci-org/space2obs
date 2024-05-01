import argparse
import pathlib
import re
import textwrap

import s2olib.shared


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


DEFAULT_MAX_EXPLANATION_LENGTH: int = 600
DEFAULT_TEXT_TPL: str = '{title}\\n\\n{explanation}\\n\\n[ {copyright} | apod.nasa.gov | {date} ]' # escape \n here in the template... e.g. \n -> \\n

TEXT_TPL_VARS: list[str] = re.findall('({[a-z]+})', DEFAULT_TEXT_TPL)

API_URL_TPL: str = 'https://api.nasa.gov/planetary/apod?count=1&api_key={nasa_api_key}'

ENTRY_FUNC: str = 'daemon'

ARGS: list[dict[str, any]] = [
    {
        'name_or_flags': ['--apod-max-explanation-length'],
        'metavar': 'NUM',
        'type': int,
        'default': DEFAULT_MAX_EXPLANATION_LENGTH,
        'help': f'Set the maximum length in characters for the explanation text. Default: {DEFAULT_MAX_EXPLANATION_LENGTH}'
    },
    {
        'name_or_flags': ['--apod-text-template'],
        'metavar': 'TEXT',
        'type': str,
        'default': DEFAULT_TEXT_TPL,
        'help': f'Specify the template for the text file. Add linebreaks with "\\n". Variables: {", ".join(TEXT_TPL_VARS)}. Default: {DEFAULT_TEXT_TPL}'
    },
]


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


def daemon(args: argparse.Namespace):
    secrets = s2olib.shared.get_secrets(args.secrets_file, ['nasa_api_key'])
    api_url = API_URL_TPL.format(**secrets)
    obs_data_file: pathlib.Path = args.cache_dir / 'apod_last_data'
    obs_image_file: pathlib.Path = args.cache_dir / 'apod_last_image'
    obs_text_file: pathlib.Path = args.cache_dir / 'apod_last_text'
    last_content_size: int = obs_data_file.stat().st_size if obs_data_file.is_file() else 0

    while True:
        s2olib.shared.msg('downloading data')
        res = s2olib.shared.fetch_remote_data(api_url, args.request_timeout, ['application/json'])

        if not res:
            s2olib.shared.msg('invalid response data')
            s2olib.shared.retry_idle(args.retry_delay)
            continue

        if len(res.content) == last_content_size:
            s2olib.shared.msg('same as before')
            s2olib.shared.endofloop_idle(args.interval)
            continue

        dump: list | dict = res.json()
        data: dict = dump[0] if dump and type(dump) == list else {}

        s2olib.shared.check_xrate(res)

        if data.get('media_type', None) != 'image':
            s2olib.shared.msg(f"skipping media type '{data.get('media_type')}'")
            s2olib.shared.retry_idle(args.retry_delay)
            continue

        if 'tomorrow\'s picture:' in data.get('explanation', '').lower():
            s2olib.shared.msg(f"skipping bad data '{data['explanation'][0:30]}...'")
            s2olib.shared.retry_idle(args.retry_delay)
            continue

        last_content_size = len(res.content)

        s2olib.shared.msg(f'updating {obs_data_file.name}')
        obs_data_file.write_bytes(res.content)

        s2olib.shared.msg('downloading image')
        image_url = data.get('url', None)
        res = s2olib.shared.fetch_remote_data(image_url, args.request_timeout, ['image/jpeg', 'image/png', 'image/gif'])
        if not res:
            s2olib.shared.msg('download failed')
            s2olib.shared.retry_idle(args.retry_delay)
            continue

        s2olib.shared.msg(f'updating {obs_image_file.name}')
        obs_image_file.write_bytes(res.content)

        s2olib.shared.msg(f'updating {obs_text_file.name}')
        text: str = args.apod_text_template.replace('\\n', '\n').format(
            date=s2olib.shared.megastrip(data.get('date', '?')),
            title=s2olib.shared.megastrip(data.get('title', '?')),
            copyright=s2olib.shared.megastrip(data.get('copyright', '?')),
            explanation=textwrap.shorten(s2olib.shared.megastrip(data.get('explanation', '')), args.apod_max_explanation_length),
        )
        obs_text_file.write_text(text)

        s2olib.shared.endofloop_idle(args.interval)
