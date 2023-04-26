import functools
import os
from tempfile import TemporaryFile
import timeit
from PIL import Image
import itertools

from imaginex_lambda.lib.img_lib import optimize_image
from imaginex_lambda.lib.utils import logger, get_extension

NINJA_API_KEY = ''

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

    quality = 100
    width = 100

    RESULTS = []

    with TemporaryFile() as tmp_buffer:
        or_width_options = [4096, 2048, 1024, 512]
        q_options = [100, 75, 50, 25]
        scale_options = [100, 75, 50, 25]
        for or_width in or_width_options:
            generate_image(tmp_buffer, api_key=NINJA_API_KEY, w=or_width, h=or_width)
            tmp_buffer.flush()
            img = Image.open(tmp_buffer)
            mime = get_extension(tmp_buffer)
            content_type = mime['content_type']
            extension = mime['extension']
            run_dict = {
                'original_size': os.stat(tmp_buffer.name).st_size,
                'original_width': or_width,
                'original_height': or_width,
                'img_format': extension,
                'results': []
            }

            for q, scale in itertools.product(q_options, scale_options):
                requested_width = int(or_width * (scale / 100))

                callable_fun = functools.partial(optimize_image, tmp_buffer,
                                                 extension,
                                                 q,
                                                 requested_width,
                                                 None)

                t = timeit.Timer(callable_fun)
                res_time = t.timeit(number=1)

                # Check
                image_data = callable_fun.__call__()

                opt_image = Image.open(BytesIO(image_data))
                assert opt_image.width == requested_width

                run_dict_results = {
                    'new_size': len(image_data),
                    'req_q': q,
                    'req_width': requested_width,
                    'opt_height': opt_image.height,
                    'time': res_time
                }
                run_dict['results'].append(run_dict_results)

                BENCHMARK['number_of_tests'] += 1
            BENCHMARK['run'].append(run_dict)
    logger.info("Benchmark ended...")
