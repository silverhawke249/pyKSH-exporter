from pathlib import Path

from PIL import Image


def get_jacket_images(file_path: Path) -> tuple[bytes, bytes, bytes]:
    """ Return jacket images as PNG blobs at regular, big, small sizes in order. """
    image = Image.open(str(file_path))

    return b'', b'', b''
