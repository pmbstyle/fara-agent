"""Run the Fara agent with a task"""
import asyncio
import argparse
import json
import logging

from agent import FaraAgent


logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    parser = argparse.ArgumentParser(description="Run Fara agent with LM Studio")
    parser.add_argument(
        "--task",
        type=str,
        required=True,
        help="The task for the agent to perform"
    )
    parser.add_argument(
        "--headful",
        action="store_true",
        help="Run browser in headful mode (show GUI)"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.json",
        help="Path to config file"
    )
    
    args = parser.parse_args()
    
    # Load config
    with open(args.config) as f:
        config = json.load(f)
    
    # Create and run agent
    agent = FaraAgent(
        config=config,
        headless=not args.headful,
        logger=logger
    )
    
    try:
        await agent.start()
        await agent.run(args.task)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
    finally:
        await agent.close()


if __name__ == "__main__":
    asyncio.run(main())

