import argparse
import asyncio
import sys
from pathlib import Path

from loguru import logger

import config
from exporter import export_products_to_excel
from scraper import BooksScraper


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="books-scraper",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--max-pages", type=int, default=config.DEFAULT_MAX_PAGES)
    parser.add_argument("--output-dir", type=Path, default=config.OUTPUT_DIR)
    parser.add_argument("--logs-dir", type=Path, default=config.LOGS_DIR)
    parser.add_argument("--concurrency", type=int, default=config.MAX_CONCURRENT_REQUESTS)
    parser.add_argument("--request-delay", type=float, default=config.REQUEST_DELAY)
    parser.add_argument("--no-color", action="store_true")
    return parser.parse_args(argv)


async def run(args):
    scraper = BooksScraper(
        base_url=config.BASE_URL,
        max_concurrent=args.concurrency,
        request_delay=args.request_delay,
    )
    try:
        products = await scraper.scrape(max_pages=args.max_pages)
    finally:
        await scraper.close()

    if not products:
        logger.warning("no products found")
        return None

    return export_products_to_excel(products, output_dir=args.output_dir)


def main(argv=None):
    args = parse_args(argv)
    config.setup_logger(logs_dir=args.logs_dir, colorize=not args.no_color)

    try:
        output_path = asyncio.run(run(args))
    except KeyboardInterrupt:
        return 130
    except Exception:
        logger.exception("unhandled error")
        return 1

    if output_path is None:
        return 1
    logger.success("done: {}", output_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
