"""Reads PNG files, for comparing a screenshot with Mekanism's art. Python's own zlib is enough."""

import struct
import zlib
from pathlib import Path

CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
GREY, RGB, PALETTE, GREY_ALPHA, RGBA = 0, 2, 3, 4, 6


class Image:
    def __init__(self, path: Path) -> None:
        data = Path(path).read_bytes()
        at, chunks, palette, alphas = 8, b"", b"", b""
        while at < len(data):
            size = struct.unpack(">I", data[at : at + 4])[0]
            kind = data[at + 4 : at + 8]
            body = data[at + 8 : at + 8 + size]
            at += 12 + size
            if kind == b"IHDR":
                self.width, self.height, depth, colour = struct.unpack(">IIBB", body[:10])
                if body[12]:
                    raise ValueError(f"{path}: interlaced")
            elif kind == b"IDAT":
                chunks += body
            elif kind == b"PLTE":
                palette = body
            elif kind == b"tRNS":
                alphas = body
        channels = CHANNELS[colour]
        if depth == 16:
            raise ValueError(f"{path}: 16 bits a channel")
        stride = (self.width * channels * depth + 7) // 8
        distance = max(1, channels * depth // 8)
        raw = zlib.decompress(chunks)
        rows, above, position = [], bytes(stride), 0
        for _ in range(self.height):
            kind = raw[position]
            row = bytearray(raw[position + 1 : position + 1 + stride])
            position += 1 + stride
            for x in range(stride):
                left = row[x - distance] if x >= distance else 0
                up = above[x]
                corner = above[x - distance] if x >= distance else 0
                if kind == 1:
                    row[x] = (row[x] + left) & 255
                elif kind == 2:
                    row[x] = (row[x] + up) & 255
                elif kind == 3:
                    row[x] = (row[x] + (left + up) // 2) & 255
                elif kind == 4:
                    guess = left + up - corner
                    a, b, c = abs(guess - left), abs(guess - up), abs(guess - corner)
                    best = left if a <= b and a <= c else up if b <= c else corner
                    row[x] = (row[x] + best) & 255
            rows.append(bytes(row))
            above = row
        self._rows, self._channels, self._colour = rows, channels, colour
        self._depth, self._palette, self._alphas = depth, palette, alphas

    def _sample(self, row: bytes, x: int) -> int:
        bit = x * self._depth
        byte = row[bit // 8]
        return (byte >> (8 - self._depth - bit % 8)) & ((1 << self._depth) - 1)

    def pixel(self, x: int, y: int) -> tuple[int, int, int, int]:
        row = self._rows[y]
        if self._colour == PALETTE:
            index = self._sample(row, x)
            r, g, b = self._palette[index * 3 : index * 3 + 3]
            alpha = self._alphas[index] if index < len(self._alphas) else 255
            return r, g, b, alpha
        if self._colour == GREY:
            level = self._sample(row, x) * 255 // ((1 << self._depth) - 1)
            return level, level, level, 255
        c = self._channels
        p = row[x * c : x * c + c]
        if self._colour == GREY_ALPHA:
            return p[0], p[0], p[0], p[1]
        return (*p[:3], p[3] if c == 4 else 255)
