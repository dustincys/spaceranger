#
# Copyright (c) 2019 10X Genomics, Inc. All rights reserved.
#

"""Functions and classes for loading and manipulating images."""

import base64
import tempfile
import os

from PIL import Image

def _base64_encode_image(filename):
    """
    Opens a file using PIL and returns it encoded as a base64 string
    :param filename:
    :return:
    """
    image_show = open(filename, "rb")
    image_show = image_show.read()
    encoded_string = base64.b64encode(image_show).decode('utf-8')
    return "data:image/jpg;base64," + encoded_string

class WebImage(object):
    """A class for working with and investigating simple image files"""
    def __init__(self, filename, cropbox=None, markersize=None):
        """
        Create a new instance that can base64 encode the image and give coordinates
        :param filename: Image file name
        :param cropbox: optional [ x0, y0, x1, y1 ] just held as an attribute,
        :               defaults to whole image
        :param markersize: optional marker size for plotly for plotting a capture area spot
        """
        img = Image.open(filename)
        self._base64 = _base64_encode_image(filename)
        self.filename = filename
        self.width, self.height = img.size
        self.cropbox = cropbox if cropbox is not None else [0, 0, self.width-1, self.height-1]
        self.markersize = markersize

    @property
    def base64_encoded_str(self):
        """
        :return: String for a web summary,i.e. "data:image/jpg;base64,..."
        """
        return self._base64

    def resize_and_encode_image(self, new_width=None, new_height=None):
        """
        :param new_width: New image height
        :param new_height: New image width
        :return: A base64 encoded string with the new image in it.
        """
        # TODO: We want to be able to encode this without saving to a file.
        if not new_width and not new_height:
            raise ValueError("Width and/or height must be set when resizing image.")
        elif not new_width:
            new_width = self.width * new_height / self.height
        elif not new_height:
            new_height = self.height * new_width / self.width

        _, fname = os.path.split(self.filename)
        tmp_file = os.path.join(tempfile.mkdtemp(), "tmp_" + fname)
        img = Image.open(self.filename)
        img2 = img.resize((new_width, new_height), Image.ANTIALIAS)
        img2.save(tmp_file)
        return WebImage(tmp_file)
