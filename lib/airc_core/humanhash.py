"""Human-readable hash mnemonics used by airc invites and agent labels."""

from __future__ import annotations

import argparse

DICT = (
    "ack alabama alanine alaska alpha angel apart april arizona arkansas artist asparagus aspen august autumn avocado bacon bakerloo batman beer berlin beryllium black blossom blue bluebird bravo bulldog burger butter california carbon cardinal carolina carpet cat ceiling cello center charlie chicken coffee cola cold colorado comet connecticut crazy cup dakota december delaware delta diet don double early earth east echo edward eight eighteen eleven emma enemy equal failed fanta fillet finch fish five fix floor florida football four fourteen foxtrot freddie friend fruit gee georgia glucose golf green grey hamper happy harry hawaii helium high hot hotel hydrogen idaho illinois india indigo ink iowa island item jersey jig johnny juliet july jupiter kansas kentucky kilo king kitten lactose lake lamp lemon leopard lima lion lithium london louisiana low magazine magnesium maine mango march mars maryland massachusetts may mexico michigan mike minnesota mirror missouri mobile mockingbird monkey montana moon mountain muppet music nebraska neptune network nevada nine nineteen nitrogen north november nuts october ohio oklahoma one orange oranges oregon oscar oven oxygen papa paris pasta pennsylvania pip pizza pluto potato princess purple quebec queen quiet red river robert robin romeo rugby sad salami saturn september seven seventeen shade sierra single sink six sixteen skylark snake social sodium solar south spaghetti speaker spring stairway steak stream summer sweet table tango ten tennessee tennis texas thirteen three timing triple twelve twenty two uncle undress uniform uranus utah vegan venus vermont victor video violet virginia washington west whiskey white william winner winter wisconsin wolfram wyoming xray yankee yellow zebra zulu"
).split()


def humanhash(hex_input: str, n_words: int = 4) -> str:
    if not hex_input:
        raise ValueError("empty input")
    if n_words < 1:
        raise ValueError("n_words must be >= 1")
    if len(hex_input) % 2:
        hex_input = f"0{hex_input}"
    try:
        data = bytes.fromhex(hex_input)
    except ValueError as exc:
        raise ValueError("input must be hex") from exc
    if not data:
        raise ValueError("empty input")

    seg_size = max(len(data) // n_words, 1)
    words: list[str] = []
    for seg in range(n_words):
        start = seg * seg_size
        end = len(data) if seg == n_words - 1 else start + seg_size
        acc = 0
        for value in data[start:end]:
            acc ^= value
        words.append(DICT[acc])
    return "-".join(words)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="airc_core.humanhash")
    parser.add_argument("hex_input")
    parser.add_argument("--words", type=int, default=4)
    args = parser.parse_args(argv)
    print(humanhash(args.hex_input, args.words))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
