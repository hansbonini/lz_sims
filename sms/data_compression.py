import binascii
import sys

from romhacking.common import BitArray, RingBuffer, Compression, LZSS

class LZSIMS(LZSS):
    """
        Class to manipulate LZSIMS Compression

        Games where this compression is found:
            - [SMS] Disney's Alladin
            - [SMS] Master of Darkness
            - [SMS] Masters of Combat
            - [SMS] Ninja Gaiden
    """

    debug = []

    signature = b"\xF5\xCB\x6F\x28\x09\xE6\x07\x47\x7E\x23\x4F\xC3"

    def __init__(self, input_data):
        super(LZSIMS, self).__init__(input_data)

    def lz_unpack(self, temp=0):
        lzpair = self.DATA.read_8()
        position = self._window.CURSOR - ((lzpair >> 4) | temp)
        length = ((lzpair & 0xF) + 2)
        for x in range(length):
            self.append(self._window._buffer[(position+x) & 0x7FF])
        return 1

    def rle_unpack(self, length=0, repetitions=0):
        value = bytearray()
        length += 1
        repetitions += 2
        for x in range(length):
            value += self.DATA.read_8().to_bytes(1, 'big')
        for repeat in range(repetitions):
            for b in value:
                self.append(b)
        return length

    def raw_unpack(self, length=0):
        length += 1
        for x in range(length):
            value = self.DATA.read_8()
            self.append(value)
        return length

    def decompress(self, offset=0, size=0):
        self.DATA.set_offset(offset)
        self.DATA.ENDIAN = '<'
        self._window = RingBuffer(0x800, 0x0, 0x0)
        self._output = bytearray()
        size = self.DATA.read_16()
        self._decoded = 0
        while self._decoded < size:
            try:
                temp = self.DATA.read_8()
                if not (temp >> 7) & 0x1:
                    self._decoded += self.lz_unpack((temp << 4) & 0xFF0) + 1
                elif not (temp >> 6) & 0x1:
                    self._decoded += self.raw_unpack((temp & 0x3F)) + 1
                elif not (temp >> 5) & 0x1:
                    self._decoded += self.rle_unpack((temp >> 3)
                                                     & 0x3, (temp & 0x7)) + 1
                else:
                    repetitions = self.DATA.read_8()
                    self._decoded += self.rle_unpack((temp >> 3)
                                                     & 0x3, repetitions) + 2
            except:
                break

        return self._output

    def compress(self):
        self.DATA.ENDIAN = '<'
        self._window = RingBuffer(0x800, 0x0, 0x0)
        self._buffer = bytearray()
        self._output = bytearray()
        self._output.append(0x0)
        self._output.append(0x0)
        self._encoded = 0
        self.LOOKAHEAD = 0b1111
        self.MIN_LENGTH = 2
        self.di = 0
        while self._encoded < self.DATA.SIZE:
            # Search for RLE match
            rle_match = self.find_best_rle_match()
            # Search for LZ matches
            lz_match = self.find_best_lz_match(llimit=True)
            if rle_match[0]*rle_match[1] < self.MIN_LENGTH and lz_match[1] < self.MIN_LENGTH:
                self.raw_pack(rle_match, lz_match)
            else:
                # Otimization checks to compress more than original
                if (
                    rle_match[0]*rle_match[1] <= len(self._buffer)+1
                    and lz_match[1] <= len(self._buffer)+1
                    and rle_match[0]*rle_match[1] <= self.MIN_LENGTH
                    and lz_match[1] <= self.MIN_LENGTH
                ):
                    self.raw_pack(rle_match, lz_match)
                else:
                    if len(self._buffer) > 0:
                        self.flush_raw(rle_match, lz_match)
                    temp1 = self.rle_pack(rle_match, lz_match)
                    temp2 = self.lz_pack(rle_match, lz_match)
                    if (
                        rle_match[0]*rle_match[1] >= self.MIN_LENGTH
                        and lz_match[1] >= self.MIN_LENGTH
                    ):
                        if rle_match[0]*rle_match[1] >= lz_match[1]:
                            if len(temp1) <= len(temp2):
                                if rle_match[0]*rle_match[1] >= lz_match[1] and len(temp1) < 3:
                                    self.append_data_rle(temp1, rle_match)
                                else:
                                    self.append_data_lz(temp2, lz_match)
                            else:
                                if rle_match[0]*rle_match[1] > lz_match[1] and len(temp1) <= 3:
                                    self.append_data_rle(temp1, rle_match)
                                else:
                                    self.append_data_lz(temp2, lz_match)
                        else:
                            self.append_data_lz(temp2, lz_match)
                    elif (
                        rle_match[0]*rle_match[1] < self.MIN_LENGTH
                        and lz_match[1] >= self.MIN_LENGTH
                    ):
                        self.append_data_lz(temp2, lz_match)
                    else:
                        self.append_data_rle(temp1, rle_match)
        self._output[1] = len(self._output) >> 8
        self._output[0] = len(self._output) & 0xFF
        return self._output

    def append_data_rle(self, data=bytearray(), rle_match=(0, 0)):
        self._output += data
        self.DATA.CURSOR += rle_match[0]*rle_match[1]
        self._encoded += rle_match[0]*rle_match[1]

    def append_data_lz(self, data=bytearray(), lz_match=(0, 0)):
        self._output += data
        self.DATA.CURSOR += lz_match[1]
        self._encoded += lz_match[1]

    def lz_pack(self, rle_match, lz_match):
        temp = bytearray()
        try:
            index, length = lz_match
            temp.append((index >> 4))
            temp.append(((index << 4) & 0xF0) | (length-2))
        except:
            pass
        return temp

    def rle_pack(self, rle_match, lz_match):
        temp = bytearray()
        _readed = b''
        for i in range(rle_match[0]):
            _readed += self.DATA.read_8().to_bytes(1, 'big')
        self.DATA.CURSOR -= rle_match[0]
        try:
            if rle_match[1] > 0x7:
                temp.append(0xe0 | ((rle_match[0]-1) << 3))
                temp.append(rle_match[1]-2)
            else:
                temp.append(
                    0xc0 | ((rle_match[0]-1) << 3) | (rle_match[1]-2))
            for i in range(rle_match[0]):
                temp.append(_readed[i])
        except:
            pass
        return temp

    def raw_pack(self, rle_match, lz_match):
        self._buffer.append(self.DATA.read_8())
        self._encoded += 1
        if len(self._buffer) > 0x3F:
            self.flush_raw(rle_match, lz_match)

    def flush_raw(self, rle_match, lz_match):
        self._output.append(0x80 | ((len(self._buffer)-1) & 0x3F))
        for i in range(len(self._buffer)):
            self._output.append(self._buffer[i])
        self._buffer = bytearray()

    def find_best_rle_match(self):
        _search = bytearray(self.DATA.raw)
        matches = []
        for best_length in range(min(0x7, self.DATA.SIZE-self._encoded), 0, -1):
            best_repetitions = 0
            if best_length > 0:
                for i in range(0, 0x6FF//best_length, best_length):
                    best_repetitions = i//best_length
                    total = best_length*best_repetitions
                    if not best_length < 1 and not best_repetitions < 2:
                        matches.append((best_length, best_repetitions, total))
                    if (
                        _search[self._encoded:self._encoded+best_length] !=
                        _search[self._encoded+i:self._encoded+i+best_length]
                    ):
                        break
        if len(matches) > 0:
            matches.sort(key=lambda m: m[2])
            matches.reverse()
            best_total = matches[0][2]
            matches = list(filter(lambda m: m[2] == best_total, matches))
            matches.sort(key=lambda m: m[0])
            return (matches[0][0], matches[0][1])
        return (0, 0)
