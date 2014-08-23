import argparse
import asyncio
import logging
import time

from huhhttp.fuzz import Fuzzer
from huhhttp.site import SiteServer


_logger = logging.getLogger(__name__)


def main():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('--port', default=8080, type=int)
    arg_parser.add_argument('--host', default='localhost')
    arg_parser.add_argument('--seed', default=1, type=int)
    arg_parser.add_argument('--fuzz-period', default=500, type=int)
    arg_parser.add_argument('--restart-interval', default=10000, type=int)

    args = arg_parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    fuzzer = Fuzzer(seed=args.seed, period=args.fuzz_period)
    _logger.info('Seed %s, Period %s, Interval %s',
                 args.seed, args.fuzz_period, args.restart_interval)

    while True:
        server_callback = SiteServer(fuzzer,
                                     restart_interval=args.restart_interval)
        task = asyncio.start_server(server_callback, host=args.host,
                                    port=args.port)

        server = asyncio.get_event_loop().run_until_complete(task)
        server_callback.asyncio_server = server

        asyncio.get_event_loop().run_forever()

        _logger.debug('Sleeping')
        time.sleep(1)


if __name__ == '__main__':
    main()
