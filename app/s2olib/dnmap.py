import argparse
import datetime
import pathlib

import s2olib.shared


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


IMAGE_URL_TPL: str = 'https://www.timeanddate.com/scripts/sunmap.php?iso={iso}&earth={earth}'

ENTRY_FUNC: str = 'daemon'

ARGS: list[dict[str, any]] = [
    {
        'name_or_flags': ['--dnmap-simple'],
        'action': 'store_true',
        'default': False,
        'help': 'Download the simple version of the map image. Default: download the satellite version'
    }
]


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


def daemon(args: argparse.Namespace):
    obs_image_file: pathlib.Path = args.cache_dir / 'dnmap_last_image'
    last_content_size: int = obs_image_file.stat().st_size if obs_image_file.is_file() else 0

    while True:
        img_url = IMAGE_URL_TPL.format(iso=datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y%m%dT%H%M"), earth='0' if args.dnmap_simple else '1')

        s2olib.shared.msg('downloading image')
        res = s2olib.shared.fetch_remote_data(img_url, args.request_timeout, ['image/jpeg'])
        if not res:
            s2olib.shared.msg('invalid response data')
            s2olib.shared.retry_idle(args.retry_delay)
            continue

        if len(res.content) == last_content_size:
            s2olib.shared.msg('no change')
        else:
            s2olib.shared.msg(f'updating {obs_image_file.name}')
            obs_image_file.write_bytes(res.content)
            last_content_size = len(res.content)

        s2olib.shared.endofloop_idle(args.interval)
