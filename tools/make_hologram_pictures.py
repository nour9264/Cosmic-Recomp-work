"""Make 256x256 green hologram pictures of the imported aliens for the R3 ring.

The ring's centre shows a green scan-line hologram of the hovered alien (the stock ones are
256x256 DXT5 textures in gtex_s.xbx). These are made from the same cut-out renders used for
the wheel icons (private game art, not committed): the figure's brightness becomes green, with
scan lines, a brighter rim and a soft glow."""
import argparse
from pathlib import Path
import struct
import zlib

from wheel_icon_texture import read_png

SIZE = 256
FIT = 236  # Figure height in the picture


def write_png(path, width, height, rgba):
    rows = b''.join(b'\0' + bytes(rgba[y * width * 4:(y + 1) * width * 4]) for y in range(height))

    def chunk(kind, data):
        body = kind + data
        return struct.pack('>I', len(data)) + body + struct.pack('>I', zlib.crc32(body))
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)) +
                     chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b''))


def fit(width, height, rgba, shift=0, shrink=1.0, drop=0):
    """Area-averaged copy scaled to FIT tall (or narrower), centred on the canvas: (rgb, alpha) lists."""
    scale = min(FIT / height, (SIZE - 40) / width) * shrink
    out_w, out_h = max(1, round(width * scale)), max(1, round(height * scale))
    colors, alphas = [(0, 0, 0)] * (SIZE * SIZE), [0.0] * (SIZE * SIZE)
    left, top = (SIZE - out_w) // 2 + shift, (SIZE - out_h) // 2 + drop
    for y in range(out_h):
        y0 = int(y / scale)
        y1 = max(y0 + 1, min(height, int((y + 1) / scale)))
        for x in range(out_w):
            x0 = int(x / scale)
            x1 = max(x0 + 1, min(width, int((x + 1) / scale)))
            r = g = b = a = count = 0
            for yy in range(y0, y1):
                for xx in range(x0, x1):
                    at = (yy * width + xx) * 4
                    alpha = rgba[at + 3]
                    r += rgba[at] * alpha
                    g += rgba[at + 1] * alpha
                    b += rgba[at + 2] * alpha
                    a += alpha
                    count += 1
            if a:
                index = (top + y) * SIZE + left + x
                colors[index] = (r / a, g / a, b / a)
                alphas[index] = a / count / 255
    return colors, alphas


def blur(values, radius):
    """Box blur (rows, then columns) of a SIZE x SIZE float list."""
    for step, stride in ((1, SIZE), (SIZE, 1)):
        out = [0.0] * (SIZE * SIZE)
        for line in range(SIZE):
            base = line * stride
            prefix = [0.0]
            for i in range(SIZE):
                prefix.append(prefix[-1] + values[base + i * step])
            for i in range(SIZE):
                lo, hi = max(0, i - radius), min(SIZE, i + radius + 1)
                out[base + i * step] = (prefix[hi] - prefix[lo]) / (hi - lo)
        values = out
    return values


def hologram(colors, alphas):
    soft, wide = blur(alphas, 2), blur(alphas, 6)
    out = bytearray(SIZE * SIZE * 4)
    for index in range(SIZE * SIZE):
        a = alphas[index]
        r, g, b = colors[index]
        scan = 0.62 + (0.38 if (index // SIZE) % 4 < 2 else 0.0)
        light = (0.30 * r + 0.59 * g + 0.11 * b) / 255
        rim = max(0.0, a - soft[index]) * 2.4
        strength = min(1.0, (a * (0.68 + 0.50 * light) + rim) * scan)
        halo = max(0.0, wide[index] - a) * 0.6
        green = int(90 + 165 * min(1.0, light * 1.15 + rim)) if a > 0.02 or rim else 190
        opacity = min(1.0, strength * 0.95 + halo)
        out[index * 4:index * 4 + 4] = bytes((int(28 * strength + 60 * rim), min(255, green),
                                              int(48 * strength + 50 * rim), int(opacity * 255)))
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cutouts', type=Path, help='Folder with the cut-out PNGs')
    parser.add_argument('output', type=Path, help='Folder to write <alien>_holo.png into')
    parser.add_argument('--pair', nargs=2, action='append', metavar=('ALIEN', 'CUTOUT'), required=True)
    parser.add_argument('--place', nargs=4, action='append', default=[], metavar=('ALIEN', 'SHIFT', 'SHRINK', 'DROP'),
                        help='Move an alien sideways and down (pixels) and scale it, to centre its body')
    args = parser.parse_args()
    placing = {name: (int(shift), float(shrink), int(drop)) for name, shift, shrink, drop in args.place}
    args.output.mkdir(parents=True, exist_ok=True)
    for name, cutout in args.pair:
        width, height, rgba = read_png(args.cutouts / cutout)
        write_png(args.output / f'{name}_holo.png', SIZE, SIZE, hologram(*fit(width, height, rgba, *placing.get(name, (0, 1.0, 0)))))
        print('Wrote', name)


if __name__ == '__main__':
    main()
