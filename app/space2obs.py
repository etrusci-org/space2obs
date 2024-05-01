#!/usr/bin/env python3

import argparse
import importlib
import pathlib
import sys

import s2olib.shared


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


try:
    import requests
except ImportError as e:
    sys.stderr.write('missing module: requests <https://github.com/psf/requests>\n')
    exit(1)


if __name__ == '__main__':
    argparser = argparse.ArgumentParser(**s2olib.shared.ARGPARSER_SETUP)

    s2olib.shared.add_args(dest=argparser, args=[s2olib.shared.ARG_TOOL])

    for v in s2olib.shared.ARG_GROUPS:
        group = argparser.add_argument_group(title=v[0])
        s2olib.shared.add_args(dest=group, args=v[1])

    if len(sys.argv) == 1:
        argparser.print_help()
        exit(0)

    args = argparser.parse_args()

    args.cache_dir = pathlib.Path(args.cache_dir).resolve()
    args.secrets_file = pathlib.Path(args.secrets_file).resolve()

    if not args.cache_dir.is_dir():
        s2olib.shared.msg(f'cache directory path does not point to a directory: {args.cache_dir}')
        exit(1)

    if not args.secrets_file.is_file():
        s2olib.shared.msg(f'secrets file path does not point to a file: {args.secrets_file}')
        exit(1)

    try:
        s2olib.shared.disable_terminal_cursor()
        s2olib.shared.msg(f'-=[ space2obs :: {args.tool} ]=-', plain=True, end='\n\n')
        module = importlib.import_module(f's2olib.{args.tool}')
        getattr(module, module.ENTRY_FUNC)(args)
    except KeyboardInterrupt:
        s2olib.shared.msg('[quit]', start='\n')
    finally:
        s2olib.shared.enable_terminal_cursor()
