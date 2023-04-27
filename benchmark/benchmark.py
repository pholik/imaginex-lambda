import functools
import os
from datetime import datetime
from tempfile import TemporaryFile
import timeit
from PIL import Image
import itertools

import pandas
from dotenv import load_dotenv

from imaginex_lambda.lib.img_lib import optimize_image
from imaginex_lambda.lib.utils import logger, get_extension

load_dotenv()

NINJA_API_KEY = os.getenv('NINJA_API_KEY')

BENCHMARK = {
    'number_of_tests': 0,
    'run': []
}


def generate_image(buffer, api_key: str, w: int, h: int):
    import requests
    import shutil

    category = 'nature'
    api_url = f'https://api.api-ninjas.com/v1/randomimage?category={category}&width={w}&height={h}'
    response = requests.get(api_url, headers={'X-Api-Key': api_key, 'Accept': 'image/jpg'}, stream=True)
    if response.status_code == requests.codes.ok:
        shutil.copyfileobj(response.raw, buffer)
        return buffer
    else:
        print("Error:", response.status_code, response.text)


if __name__ == '__main__':
    from io import BytesIO

    logger.info("Running benchmark...")

    RESULTS = []

    or_width_options = [2048, 1024, 512, 256]
    q_options = [100, 75, 50, 25]
    scale_options = [100, 75, 50, 25]
    format_options = ['JPEG', 'PNG', 'GIF']
    calls = 1
    for img_format in format_options:
        BENCHMARK_CSV = []
        for or_width in or_width_options:
            with TemporaryFile() as tmp_buffer:
                generate_image(tmp_buffer, api_key=NINJA_API_KEY, w=or_width, h=or_width)
                tmp_buffer.flush()

                img = Image.open(tmp_buffer)
                tmp_buffer_formatted = TemporaryFile()
                img.save(tmp_buffer_formatted, format=img_format)

                tmp_buffer_formatted.flush()

                img_formatted = Image.open(tmp_buffer_formatted)

                run_dict = {
                    'original_size': f"{os.stat(tmp_buffer_formatted.name).st_size / (1 << 20):,.5f} MB",
                    'original_width': or_width,
                    'original_height': or_width,
                    'img_format': img_formatted.format,
                    'calls': calls,
                }

                for q, scale in itertools.product(q_options, scale_options):
                    requested_width = int(or_width * (scale / 100))

                    callable_fun = functools.partial(optimize_image, tmp_buffer_formatted,
                                                     img_formatted.format,
                                                     q,
                                                     requested_width,
                                                     None)

                    t = timeit.Timer(callable_fun)
                    res_time = t.timeit(number=calls)

                    # Check
                    image_data = callable_fun.__call__()

                    opt_image = Image.open(BytesIO(image_data))
                    assert opt_image.width == requested_width

                    run_dict_results = {
                        # 'new_size': len(image_data),
                        'req_q': q,
                        'req_width': requested_width,
                        'opt_height': opt_image.height,
                        'avg_time': res_time / calls,
                        'total_time': res_time
                    }

                    csv_item = {**run_dict, **run_dict_results}
                    BENCHMARK_CSV.append(csv_item)

                tmp_buffer_formatted.close()

        dataframe = pandas.DataFrame(BENCHMARK_CSV)
        logger.info(f"Saving {img_format} results for width {requested_width}...")
        dataframe.to_csv(f'results_{img_format}_{datetime.now().strftime("%m_%d_%Y_%H_%M")}.csv')

    logger.info("Benchmark ended...")
