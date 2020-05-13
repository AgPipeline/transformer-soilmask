import argparse
import pathlib
import soilmask
import cv2


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

    bounds = soilmask.get_image_file_geobounds(resolved_input_path)

    img_color = soilmask.load_image(resolved_input_path)
    bin_mask = soilmask.gen_plant_mask(color_img=img_color,
                                       kernel_size=args.kernel_size)

    rgb_mask = soilmask.gen_rgb_mask(img_color, bin_mask)
    mask_rgb = cv2.cvtColor(rgb_mask, cv2.COLOR_BGR2RGB)

    soilmask.create_geotiff(mask_rgb, bounds, output_path, nodata=None, asfloat=False)


if __name__ == '__main__':
    main()
