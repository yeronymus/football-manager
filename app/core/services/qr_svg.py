"""
Zero-dependency pure-Python ISO/IEC 18004 QR Code (Byte Mode, ECC Level L, Versions 1-10)
matrix and SVG renderer.

Designed specifically for offline SPAYD 1.0 banking QR generation without leaking IBANs
or transaction amounts to external third-party QR APIs.
"""
from typing import List, Optional, Tuple

# ISO/IEC 18004 Table 7 & 9 — ECC Level L (Single/Multi-block parameters for Versions 1..10):
# (total_data_codewords, ec_codewords_per_block, num_blocks_group1, data_cw_group1, num_blocks_group2, data_cw_group2)
_VERSION_SPECS_L: dict[int, Tuple[int, int, int, int, int, int]] = {
    1: (19, 7, 1, 19, 0, 0),
    2: (34, 10, 1, 34, 0, 0),
    3: (55, 15, 1, 55, 0, 0),
    4: (80, 20, 1, 80, 0, 0),
    5: (108, 26, 1, 108, 0, 0),
    6: (136, 18, 2, 68, 0, 0),
    7: (156, 20, 2, 78, 0, 0),
    8: (194, 24, 2, 97, 0, 0),
    9: (232, 30, 2, 116, 0, 0),
    10: (274, 18, 2, 68, 2, 69),
}

_ALIGNMENT_CENTERS: dict[int, List[int]] = {
    1: [],
    2: [6, 18],
    3: [6, 22],
    4: [6, 26],
    5: [6, 30],
    6: [6, 34],
    7: [6, 22, 38],
    8: [6, 24, 42],
    9: [6, 26, 46],
    10: [6, 28, 50],
}

# Precomputed GF(256) exp/log tables with primitive polynomial 0x11D
_GF_EXP = [0] * 512
_GF_LOG = [0] * 256
_x = 1
for _i in range(255):
    _GF_EXP[_i] = _x
    _GF_LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
for _i in range(255, 512):
    _GF_EXP[_i] = _GF_EXP[_i - 255]


def _gf_mul(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return _GF_EXP[_GF_LOG[a] + _GF_LOG[b]]


def _rs_generator_poly(degree: int) -> List[int]:
    poly = [1]
    for i in range(degree):
        next_poly = [0] * (len(poly) + 1)
        root = _GF_EXP[i]
        for j, coeff in enumerate(poly):
            next_poly[j] ^= coeff
            next_poly[j + 1] ^= _gf_mul(coeff, root)
        poly = next_poly
    return poly


def _rs_encode(data: List[int], ec_len: int) -> List[int]:
    gen = _rs_generator_poly(ec_len)
    rem = [0] * ec_len
    for byte in data:
        factor = byte ^ rem[0]
        rem = rem[1:] + [0]
        if factor != 0:
            for i in range(ec_len):
                rem[i] ^= _gf_mul(gen[i + 1], factor)
    return rem


def _select_version(byte_len: int) -> int:
    for ver in range(1, 11):
        total_cw = _VERSION_SPECS_L[ver][0]
        # Mode indicator (4 bits) + char count (8 bits for v1-9, 16 bits for v10)
        header_bits = 4 + (8 if ver <= 9 else 16)
        max_bytes = (total_cw * 8 - header_bits) // 8
        if byte_len <= max_bytes:
            return ver
    raise ValueError(f"Payload too large for QR Versions 1-10 ({byte_len} bytes)")


def _encode_codewords(payload: bytes, version: int) -> List[int]:
    total_cw, ec_len, g1_blocks, g1_cw, g2_blocks, g2_cw = _VERSION_SPECS_L[version]
    bits: List[int] = []

    def append_bits(val: int, length: int) -> None:
        for shift in range(length - 1, -1, -1):
            bits.append((val >> shift) & 1)

    # Byte mode indicator = 0100
    append_bits(0b0100, 4)
    append_bits(len(payload), 8 if version <= 9 else 16)
    for b in payload:
        append_bits(b, 8)

    capacity_bits = total_cw * 8
    terminator = min(4, capacity_bits - len(bits))
    append_bits(0, terminator)
    while len(bits) % 8 != 0:
        bits.append(0)

    data_bytes = [
        int("".join(str(bit) for bit in bits[i : i + 8]), 2)
        for i in range(0, len(bits), 8)
    ]
    pad_seq = (0xEC, 0x11)
    pad_idx = 0
    while len(data_bytes) < total_cw:
        data_bytes.append(pad_seq[pad_idx % 2])
        pad_idx += 1

    # Split into blocks and compute Reed-Solomon ECC
    blocks_data: List[List[int]] = []
    blocks_ec: List[List[int]] = []
    offset = 0
    for _ in range(g1_blocks):
        chunk = data_bytes[offset : offset + g1_cw]
        offset += g1_cw
        blocks_data.append(chunk)
        blocks_ec.append(_rs_encode(chunk, ec_len))
    for _ in range(g2_blocks):
        chunk = data_bytes[offset : offset + g2_cw]
        offset += g2_cw
        blocks_data.append(chunk)
        blocks_ec.append(_rs_encode(chunk, ec_len))

    # Interleave data codewords, then EC codewords
    interleaved: List[int] = []
    max_data_len = max(len(b) for b in blocks_data)
    for col in range(max_data_len):
        for b in blocks_data:
            if col < len(b):
                interleaved.append(b[col])
    for col in range(ec_len):
        for eb in blocks_ec:
            interleaved.append(eb[col])
    return interleaved


def _place_function_patterns(version: int) -> Tuple[List[List[Optional[bool]]], List[List[bool]]]:
    size = 17 + 4 * version
    modules: List[List[Optional[bool]]] = [[None] * size for _ in range(size)]
    is_func: List[List[bool]] = [[False] * size for _ in range(size)]

    def set_func(r: int, c: int, dark: bool) -> None:
        if 0 <= r < size and 0 <= c < size:
            modules[r][c] = dark
            is_func[r][c] = True

    def place_finder(top: int, left: int) -> None:
        for dr in range(-1, 8):
            for dc in range(-1, 8):
                rr, cc = top + dr, left + dc
                if 0 <= rr < size and 0 <= cc < size:
                    in_outer = 0 <= dr <= 6 and 0 <= dc <= 6
                    is_border = dr in (0, 6) or dc in (0, 6)
                    is_center = 2 <= dr <= 4 and 2 <= dc <= 4
                    set_func(rr, cc, in_outer and (is_border or is_center))

    place_finder(0, 0)
    place_finder(0, size - 7)
    place_finder(size - 7, 0)

    # Timing patterns
    for i in range(8, size - 8):
        set_func(6, i, i % 2 == 0)
        set_func(i, 6, i % 2 == 0)

    # Alignment patterns
    centers = _ALIGNMENT_CENTERS[version]
    for r in centers:
        for c in centers:
            if (r == 6 and c == 6) or (r == 6 and c == size - 7) or (r == size - 7 and c == 6):
                continue
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    dark = max(abs(dr), abs(dc)) in (0, 2)
                    set_func(r + dr, c + dc, dark)

    # Dark module & reserved format areas
    set_func(4 * version + 9, 8, True)
    for i in range(9):
        if i != 6:
            if not is_func[8][i]:
                set_func(8, i, False)
            if not is_func[i][8]:
                set_func(i, 8, False)
    for i in range(8):
        set_func(8, size - 1 - i, False)
    for i in range(7):
        set_func(size - 1 - i, 8, False)

    # Version info (v >= 7)
    if version >= 7:
        rem = version
        for _ in range(12):
            rem = (rem << 1) ^ ((rem >> 11) * 0x1F25)
        ver_bits = (version << 12) | rem
        for i in range(18):
            bit = bool((ver_bits >> i) & 1)
            a = size - 11 + (i % 3)
            b = i // 3
            set_func(b, a, bit)
            set_func(a, b, bit)

    return modules, is_func


def _draw_format_bits(modules: List[List[bool]], mask: int) -> None:
    size = len(modules)
    # ECC Level L indicator = 01
    data = (0b01 << 3) | mask
    rem = data
    for _ in range(10):
        rem = (rem << 1) ^ ((rem >> 9) * 0x537)
    bits = ((data << 10) | rem) ^ 0x5412

    def bit_at(i: int) -> bool:
        return bool((bits >> i) & 1)

    for i in range(6):
        modules[8][i] = bit_at(i)
    modules[8][7] = bit_at(6)
    modules[8][8] = bit_at(7)
    modules[7][8] = bit_at(8)
    for i in range(9, 15):
        modules[14 - i][8] = bit_at(i)

    for i in range(8):
        modules[8][size - 1 - i] = bit_at(i)
    for i in range(8, 15):
        modules[size - 15 + i][8] = bit_at(i)
    modules[size - 8][8] = True


def encode_qr_matrix(text: str) -> List[List[bool]]:
    """Encodes UTF-8 text into a boolean 2D QR matrix (True = dark module)."""
    payload = text.encode("utf-8")
    version = _select_version(len(payload))
    codewords = _encode_codewords(payload, version)
    base_modules, is_func = _place_function_patterns(version)
    size = len(base_modules)

    bit_stream: List[bool] = []
    for cw in codewords:
        for shift in range(7, -1, -1):
            bit_stream.append(bool((cw >> shift) & 1))

    # Zig-zag upward/downward module placement
    bit_idx = 0
    upward = True
    col = size - 1
    while col > 0:
        if col == 6:
            col -= 1
        row_iter = range(size - 1, -1, -1) if upward else range(size)
        for row in row_iter:
            for dc in (0, 1):
                cc = col - dc
                if not is_func[row][cc]:
                    dark = bit_stream[bit_idx] if bit_idx < len(bit_stream) else False
                    base_modules[row][cc] = dark
                    bit_idx += 1
        upward = not upward
        col -= 2

    # Apply Mask Pattern 0 ((row + col) % 2 == 0) — valid per ISO/IEC 18004
    final_grid: List[List[bool]] = [[False] * size for _ in range(size)]
    for r in range(size):
        for c in range(size):
            val = bool(base_modules[r][c])
            if not is_func[r][c] and (r + c) % 2 == 0:
                val = not val
            final_grid[r][c] = val

    _draw_format_bits(final_grid, mask=0)
    return final_grid


def render_qr_svg(text: str, border: int = 4, scale: int = 6) -> str:
    """Renders an ISO/IEC 18004 QR code as a compact, crisp SVG document."""
    matrix = encode_qr_matrix(text)
    size = len(matrix)
    dim = (size + border * 2) * scale
    parts: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {dim} {dim}" '
        f'width="{dim}" height="{dim}" shape-rendering="crispEdges" role="img" aria-label="QR Platba">',
        f'<rect width="{dim}" height="{dim}" fill="#ffffff"/>',
        '<path fill="#0f172a" d="',
    ]
    path_cmds: List[str] = []
    for r, row in enumerate(matrix):
        y = (r + border) * scale
        for c, dark in enumerate(row):
            if dark:
                x = (c + border) * scale
                path_cmds.append(f"M{x},{y}h{scale}v{scale}h-{scale}z")
    parts.append("".join(path_cmds))
    parts.append('"/></svg>')
    return "".join(parts)
