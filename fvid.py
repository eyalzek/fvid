#!/usr/bin/env python3

from bitstring import Bits, BitArray
from magic import Magic
import mimetypes
from PIL import Image
import glob

import numpy as np
from tqdm import tqdm
import ffmpeg

import binascii

import argparse

DELIMITER = bin(int.from_bytes("HELLO MY NAME IS ALFREDO".encode(), "big"))
FRAMES_DIR = "./fvid_frames/"


def get_bits_from_file(filepath):
    bitarray = BitArray(filename=filepath)

    # adding a delimiter to know when the file ends to avoid corrupted files
    # when retrieving
    bitarray.append(DELIMITER)

    return bitarray.bin


def get_bits_from_image(image):
    width, height = image.size

    done = False

    px = image.load()
    bits = ""

    delimiter_str = DELIMITER.replace("0b", "")
    delimiter_length = len(delimiter_str)

    pbar = tqdm(range(height), desc="Getting bits from frame")

    for y in pbar:
        for x in range(width):

            # check if we have hit the delimiter
            if bits[-delimiter_length:] == delimiter_str:
                # remove delimiter from bit data to have an exact one to one
                # copy when decoding

                bits = bits[: len(bits) - delimiter_length]

                pbar.close()

                return (bits, True)

            pixel = px[x, y]
            white = (255, 255, 255)
            black = (0, 0, 0)

            pixel_bin_rep = 0

            # for exact matches
            if pixel == white:
                pixel_bin_rep = 1
            elif pixel == black:
                pixel_bin_rep = 0
            else:
                white_diff = tuple(np.absolute(np.subtract(white, pixel)))
                # min_diff = white_diff
                black_diff = tuple(np.absolute(np.subtract(black, pixel)))

                # if the white difference is smaller, that means the pixel is closer
                # to white, otherwise, the pixel must be black
                if np.less(white_diff, black_diff).all():
                    pixel_bin_rep = 1
                else:
                    pixel_bin_rep = 0

            # adding bits
            bits += str(pixel_bin_rep)

    return (bits, done)


def get_bits_from_video(video_filepath):
    # get image sequence from video
    image_sequence = []

    ffmpeg.input(video_filepath).output(
        f"{FRAMES_DIR}decoded_frames%03d.png"
    ).run(quiet=True)

    for filename in glob.glob(f"{FRAMES_DIR}decoded_frames*.png"):
        image_sequence.append(Image.open(filename))

    # process = (
    #     ffmpeg.input(video_filepath)
    #     .output("pipe:", format="rawvideo", pix_fmt="rgb24")
    #     .run_async(pipe_stdout=True)
    # )

    # image = Image.frombytes(
    #     size=(1920, 1080), data=process.stdout.read(1920 * 1080), mode="1"
    # )

    # image.save("image.png")

    # get pixels from each still frame and append to one big array
    bits = ""
    sequence_length = len(image_sequence)

    for index in range(sequence_length):
        b, done = get_bits_from_image(image_sequence[index])

        bits += b

        if done:
            break

    return bits


def save_bits_to_file(filepath, bits):
    # get file extension

    bitstring = Bits(bin=bits)

    mime = Magic(mime=True)
    mime_type = mime.from_buffer(bitstring.tobytes())

    with open(
        f"{filepath}/file{mimetypes.guess_extension(type=mime_type)}", "wb"
    ) as f:
        bitstring.tofile(f)


def make_image(bit_set, resolution=(1920, 1080)):

    width, height = resolution

    image = Image.new("1", (width, height))
    image.putdata(bit_set)

    return image


def split_list_by_n(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i: i + n]


def make_image_sequence(bitstring, resolution=(1920, 1080)):
    width, height = resolution

    # split bits into sets of width*height to make (1) image
    set_size = width * height

    # bit_sequence = []
    bit_sequence = split_list_by_n(list(map(int, bitstring)), width * height)
    image_bits = []

    # using bit_sequence to make image sequence

    image_sequence = []

    for bit_set in bit_sequence:
        image_sequence.append(make_image(bit_set))

    return image_sequence


def make_video(output_filepath, image_sequence):
    # image1 = np.stack([imageio.imread("image0_rend.png")] * 3, 2)
    # # image2 = imageio.imread("image1.png")
    # # image3 = imageio.imread("imageio:immunohistochemistry.png")

    # w = imageio.get_writer(filepath, fps=1, macro_block_size=None)

    # w.append_data(image1)
    # # w.append_data(image2)
    # # w.append_data(image3)

    # w.close()

    # process = (
    #     ffmpeg.input("pipe:", pattern_type="glob", framerate=25)
    #     .output(filepath, vcodec="libx264rgb")
    #     .run_async(pipe_stdin=True)
    # )

    # for image in image_sequence:
    #     process.communicate(input=image.tobytes())

    # process.communicate(input="*.png")

    frames = glob.glob(f"{FRAMES_DIR}encoded_frames*.png")

    # for one frame
    if len(frames) == 1:
        ffmpeg.input(frames[0], loop=1, t=1).output(
            output_filepath, vcodec="libx264rgb"
        ).run(quiet=True)

    else:
        ffmpeg.input(
            f"{FRAMES_DIR}encoded_frames*.png",
            pattern_type="glob",
            framerate="1/5",
        ).output(output_filepath, vcodec="libx264rgb").run(quiet=True)


def get_output_path(args):
    setup(args.output)
    return args.output

def encode(args):
    # get bits from file
    bits = get_bits_from_file(args.input)

    # create image sequence
    image_sequence = make_image_sequence(bits)

    # save images
    for index in range(len(image_sequence)):
        image_sequence[index].save(
            f"{FRAMES_DIR}encoded_frames_{index}.png"
        )

    make_video("%s/file.mp4" % get_output_path(args), image_sequence)


def decode(args):
    bits = get_bits_from_video(args.input)

    save_bits_to_file(get_output_path(args), bits)


def cleanup():
    # remove frames
    import shutil

    shutil.rmtree(FRAMES_DIR)


def setup(directory=FRAMES_DIR):
    import os

    if not os.path.exists(directory):
        os.makedirs(directory)


def parse_args():
    parser = argparse.ArgumentParser(description="save files as videos")
    parser.add_argument("action", help="encode file as video, or decode file from video",
                        choices=("encode", "decode"))
    parser.add_argument("-i", "--input", help="input file", required=True)
    parser.add_argument("-o", "--output", help="output path", default="./")

    return parser.parse_args()


def main():
    args = parse_args()
    print(args)
    setup()
    try:
        globals()[args.action](args)
    finally:
        cleanup()


if __name__ == "__main__":
    main()
