import argparse
import pathlib

import s2olib.shared


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


CAMERAS: dict[tuple[str, str] | None] = {
    'all': None,
    'c2': ('LASCO C2', 'https://soho.nascom.nasa.gov/data/realtime/c2/1024/latest.jpg'),
    'c3': ('LASCO C3', 'https://soho.nascom.nasa.gov/data/realtime/c3/1024/latest.jpg'),
    'eit_171': ('EIT 171', 'https://soho.nascom.nasa.gov/data/realtime/eit_171/1024/latest.jpg'),
    'eit_195': ('EIT 195', 'https://soho.nascom.nasa.gov/data/realtime/eit_195/1024/latest.jpg'),
    'eit_284': ('EIT 284', 'https://soho.nascom.nasa.gov/data/realtime/eit_284/1024/latest.jpg'),
    'eit_304': ('EIT 304', 'https://soho.nascom.nasa.gov/data/realtime/eit_304/1024/latest.jpg'),
    'hmi_igr': ('SDO/HMI Continuum', 'https://soho.nascom.nasa.gov/data/realtime/hmi_igr/1024/latest.jpg'),
    'hmi_mag': ('SDO/HMI Magnetogram', 'https://soho.nascom.nasa.gov/data/realtime/hmi_mag/1024/latest.jpg'),
}

DEFAULT_CAMERAS_CHOICE: list[str] = ['all']

ENTRY_FUNC: str = 'daemon'

ARGS: list[dict[str, any]] = [
    {
        'name_or_flags': ['--soho-cameras'],
        'metavar': 'ID',
        'type': str,
        'nargs': '+',
        'choices': CAMERAS.keys(),
        'default': DEFAULT_CAMERAS_CHOICE,
        'help': f'Specify one or more camera IDs to download images from. Choices: {", ".join(CAMERAS.keys())}. Default: {" ".join(DEFAULT_CAMERAS_CHOICE)}'
    },
]


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


def daemon(args: argparse.Namespace):
    cache_dir: pathlib.Path = args.cache_dir

    cameras: dict[tuple[str, str]] = {}
    if 'all' in args.soho_cameras:
        cameras = CAMERAS
        del cameras['all']
    else:
        for id, cam in CAMERAS.items():
            if id in args.soho_cameras: cameras[id] = cam

    while True:
        for id, cam in cameras.items():
            img_url = cam[1]
            obs_image_file = cache_dir / f'soho_last_{id}_image'
            last_content_size: int = obs_image_file.stat().st_size if obs_image_file.is_file() else 0

            s2olib.shared.msg(f'downloading {cam[0]} image')
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

        s2olib.shared.endofloop_idle(args.interval)
