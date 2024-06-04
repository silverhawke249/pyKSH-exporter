"""
Classes and functions that handle images and image processing for the GUI.
"""
import construct as cs

from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

from PIL import Image

__all__ = [
    "BG_HEIGHT",
    "BG_WIDTH",
    "GMBGHandler",
    "get_game_backgrounds",
    "get_jacket_images",
]

BG_WIDTH = 134
"""Width of the packed image file."""
BG_HEIGHT = 236
"""Height of the packed image file."""
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
    """Handler class for game background images."""

    redirects: dict[int, int] = field(default_factory=dict)
    images: dict[int, list[Image.Image]] = field(default_factory=dict)

    def has_image(self, bg_no: int) -> bool:
        """
        Check if a given background ID is present.

        :param bg_no: Background ID, as an `int`.
        :returns: `True` if the background image with that ID is present, `False` otherwise.
        """
        return bg_no in self.redirects or bg_no in self.images

    def get_images(self, bg_no: int) -> list[list[float]]:
        """
        Fetch a preloaded background image.

        :param bg_no: Background ID, as an `int`.
        :returns: The background image data, as a flattened list of pixel color values.
            Returns a black image if that ID is not present.
        """
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
    """
    Load game backgrounds from packed data.

    This function should only be called once.

    :returns: A :class:`~exporter.images.GMBGHandler` instance.
    """
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


def get_jacket_images(file_path: Path) -> tuple[bytes, bytes, bytes, bytes]:
    """
    Return jacket images as PNG blobs at regular, big, small sizes, in that order.

    Specifically:
     - Big size: 676x676
     - Regular size: 300x300
     - IFS size: 128x128
     - Small size: 108x108

    :param file_path: Path to image file.
    :returns: 3-tuple of bytes buffer, each containing a PNG-encoded image.
    """
    image = Image.open(str(file_path))

    image_r = image.resize((300, 300), Image.BICUBIC)
    image_b = image.resize((676, 676), Image.BICUBIC)
    image_t = image.resize((128, 128), Image.BICUBIC)
    image_s = image.resize((108, 108), Image.BICUBIC)

    fobj_r = BytesIO()
    fobj_b = BytesIO()
    fobj_t = BytesIO()
    fobj_s = BytesIO()

    image_r.save(fobj_r, format="png")
    image_b.save(fobj_b, format="png")
    image_t.save(fobj_t, format="png")
    image_s.save(fobj_s, format="png")

    return fobj_r.getvalue(), fobj_b.getvalue(), fobj_t.getvalue(), fobj_s.getvalue()
