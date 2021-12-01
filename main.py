#!/usr/bin/python
# -*- coding: utf-8 -*-
import argparse
import sys
import textwrap
from os import SEEK_CUR, SEEK_END, SEEK_SET
from romhacking.common import TBL
from sms.common import ROM
from sms.data_compression import *
from utils.common import *

cmd = argparse.ArgumentParser(
      formatter_class=argparse.RawDescriptionHelpFormatter,
      description=textwrap.dedent('''\
            [SNES] SIMS Compressor / Decompressor
            ----------------------------------------------
            Tool for decompress and recompress graphics
            from games developed by SIMS using LZ+RLE
            algorithm.
            ----------------------------------------------
            List of know compatible games;
            - [SMS] Disney's Alladin
            - [SMS] Master of Darkness
            - [SMS] Masters of Combat
            - [SMS] Ninja Gaiden
            ----------------------------------------------
            For decompress:
                python main.py D rom decompressed_file offset
            For compress:
                python main.py C rom decompressed_file offset_to_be_inserted_in_rom
        ''')
  )


def decompress(rom_path, decompressed_data_path, codec=None, *args):
    rom = ROM(rom_path, 'msb')
    algorithm = None
    for compression in FindAllSubclasses(Compression):
        if compression[1] == codec:
            algorithm = compression[0](rom)
    if algorithm:
        out = open(decompressed_data_path, 'wb')
        data = algorithm.decompress(*args)
        data_len = len(data)
        print('[INFO] Decompressed Size: {:08x}'.format(data_len))
        out.seek(0, 0)
        out.write(data)
        out.close()
        print('[INFO] Finished!')

def compress(rom_path, decompressed_data_path, codec=None, *args):
    offset = args[0]
    rom = open(rom_path, 'r+b')
    input = ROM(decompressed_data_path, 'msb')
    algorithm = None
    for compression in FindAllSubclasses(Compression):
        if compression[1] == codec:
            algorithm = compression[0](input)
    if algorithm:
        data = algorithm.compress()
        data_len = len(data)
        print('[INFO] Compressed Size: {:08x}'.format(data_len))
        rom.seek(offset, 0)
        rom.write(data)
        rom.close()
        input.close()
        print('[INFO] Finished!')

if __name__ == "__main__":

    cmd.add_argument(
        'option',
        nargs='?',
        type=str,
        default=None,
        help='"C" for Compression / "D" for Decompression'
    )

    cmd.add_argument(
        'rom',
        nargs='?',
        type=argparse.FileType('rb'),
        default=sys.stdin,
        help='Sega Master System / Sega Mark III ROM'
    )

    cmd.add_argument(
        'output',
        nargs='?',
        type=str,
        default=None,
        help='Decompressed file.'
    )

    cmd.add_argument(
        'offset',
        nargs='?',
        type=lambda x: int(x, 0),
        default=None,
        help='Offset'
    )

    args = cmd.parse_args()
    print(cmd.description)
    if args.option not in ['C','D']:
        print('[ERROR] Option must be "C" for Compression or "D" for Decompression')
        sys.exit(0)
    if args.rom.name == '<stdin>':
        print('[ERROR] An Sega Master System / Sega Mark III must be specified')
        sys.exit(0)
    if args.output == None:
        print('[ERROR] An Output File must be specified')
        sys.exit(0)
    if args.offset == None:
        print('[ERROR] An Offset must be specified')
        sys.exit(0)
    if (args.option == 'D'):
        print('[INFO] Decompressing at {:08x}...'.format(args.offset))
        decompress(args.rom.name, args.output, 'LZSIMS', args.offset)
    else:
        print('[INFO] Compressing and inserting at {:08x}...'.format(args.offset))
        compress(args.rom.name, args.output, 'LZSIMS', args.offset)