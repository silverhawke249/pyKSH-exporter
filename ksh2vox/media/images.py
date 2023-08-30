from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

import construct as cs

from PIL import Image

BG_WIDTH, BG_HEIGHT = 134, 236
PackedGMBGStruct = cs.Struct(
    "info"
    / cs.Struct(
        cs.Const(b"info"),
        "indices_size" / cs.Rebuild(cs.Int16ul, cs.len_(cs.this.indices)),
        "indices" / cs.Int16ul[cs.this.indices_size],
        "bg_count_size" / cs.Rebuild(cs.Int16ul, cs.len_(cs.this.bg_count_pairs)),
        "bg_count_pairs" / cs.Array(cs.this.bg_count_size, cs.Int16ul[2]),
        "redir_size" / cs.Rebuild(cs.Int16ul, cs.len_(cs.this.redir_pairs)),
        "redir_pairs" / cs.Array(cs.this.redir_size, cs.Int16ul[2]),
    ),
    "gmbg"
    / cs.Struct(
        cs.Const(b"gmbg"),
        "count" / cs.Rebuild(cs.Int16ul, cs.len_(cs.this.blobs)),
        "blobs"
        / cs.Struct("size" / cs.Rebuild(cs.Int32ul, cs.len_(cs.this.blob)), "blob" / cs.Bytes(cs.this.size))[
            cs.this.count
        ],
    ),
)


@dataclass
class GMBGHandler:
    redirects: dict[int, int] = field(default_factory=dict)
    images: dict[int, list[Image.Image]] = field(default_factory=dict)

    def has_image(self, bg_no: int) -> bool:
        return bg_no in self.redirects or bg_no in self.images

    def get_images(self, bg_no: int) -> list[list[float]]:
        if bg_no in self.redirects:
            image_blobs = self.images[self.redirects[bg_no]]
        elif bg_no in self.images:
            image_blobs = self.images[bg_no]
        else:
            return [[0.0, 0.0, 0.0, 1.0] * BG_WIDTH * BG_HEIGHT]

        images_pixels: list[list[float]] = []
        for image_blob in image_blobs:
            images_pixels.append([p / 255 for rgba in image_blob.getdata() for p in rgba])

        return images_pixels


def get_game_backgrounds() -> GMBGHandler:
    handler = GMBGHandler()

    parsed_struct = PackedGMBGStruct.parse_file("resources/gmbg.dat")
    blob_iter = iter(parsed_struct.gmbg.blobs)
    image_counts = dict(parsed_struct.info.bg_count_pairs)
    for i in parsed_struct.info.indices:
        image_blobs = []
        c = image_counts[i]
        for _ in range(c):
            blob = BytesIO(next(blob_iter).blob)
            image_blobs.append(Image.open(blob, formats=["png"]).convert("RGBA"))

        handler.images[i] = image_blobs

    handler.redirects = dict(parsed_struct.info.redir_pairs)

    return handler


def get_jacket_images(file_path: Path) -> tuple[bytes, bytes, bytes]:
    """Return jacket images as PNG blobs at regular, big, small sizes, in that order."""
    image = Image.open(str(file_path))

    image_r = image.resize((300, 300), Image.BICUBIC)
    image_b = image.resize((676, 676), Image.BICUBIC)
    image_s = image.resize((108, 108), Image.BICUBIC)

    fobj_r = BytesIO()
    fobj_b = BytesIO()
    fobj_s = BytesIO()

    image_r.save(fobj_r, format="png")
    image_b.save(fobj_b, format="png")
    image_s.save(fobj_s, format="png")

    return fobj_r.getvalue(), fobj_b.getvalue(), fobj_s.getvalue()
