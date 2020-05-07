import argparse
import pathlib
import soilmask


def main():
    parser = argparse.ArgumentParser(
        description='Calculate a soil mask from a GeoTIFF')
    parser.add_argument('filename', help='name of the file to process')
    parser.add_argument('--output-file', default='soilmask-output.npz',
                        help='Path of the resulting output file')
    parser.add_argument('--kernel-size', type=int, default=3,
                        help='masking kernel size')
    args = parser.parse_args()
    input_path = pathlib.Path(args.filename)
    resolved_input_path = input_path.resolve(strict=True)
    output_path = pathlib.Path(args.output_file)

    img_color = soilmask.load_image(resolved_input_path)
    bin_mask = soilmask.gen_plant_mask(color_img=img_color,
                                       kernel_size=args.kernel_size)

    soilmask.save_mask(output_path, bin_mask)


if __name__ == '__main__':
    main()
