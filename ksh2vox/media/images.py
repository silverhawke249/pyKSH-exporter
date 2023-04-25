from io import BytesIO
from pathlib import Path

from PIL import Image


def get_jacket_images(file_path: Path) -> tuple[bytes, bytes, bytes]:
    """ Return jacket images as PNG blobs at regular, big, small sizes in order. """
    image = Image.open(str(file_path))

    image_r = image.resize((300, 300), Image.Resampling.BICUBIC)
    image_b = image.resize((676, 676), Image.Resampling.BICUBIC)
    image_s = image.resize((108, 108), Image.Resampling.BICUBIC)

    fobj_r = BytesIO()
    fobj_b = BytesIO()
    fobj_s = BytesIO()

    image_r.save(fobj_r, format='png')
    image_b.save(fobj_b, format='png')
    image_s.save(fobj_s, format='png')

    return fobj_r.getvalue(), fobj_b.getvalue(), fobj_s.getvalue()
