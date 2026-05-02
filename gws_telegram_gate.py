"""
Standalone Two-Way Telegram Human Gate for gworkspace-agent.
Run with: python gws_telegram_gate.py --task "your task here"
Or import TelegramHumanGate directly for programmatic use.
"""
import argparse
import asyncio
import logging

from gws_assistant.human_gate.factory import get_human_gate

logging.basicConfig(level=logging.INFO)

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=False, help="Task description to run with human gate")
    parser.add_argument("--demo", action="store_true", help="Run interactive demo of all gate methods")
    args = parser.parse_args()

    if not args.task and not args.demo:
        parser.error("Either --task or --demo must be provided")

    gate = get_human_gate()
    await gate.start()

    try:
        if args.demo:
            await gate.notify("🚀 Human Gate demo started!")

            try:
                name = await gate.ask_text("What is your name?", context="Personalization setup")
                await gate.notify(f"Hello {name}!")

                approved = await gate.ask_approval(
                    action="Delete temp files",
                    details="Will remove /tmp/gws_cache - 45MB"
                )
                await gate.notify(f"You {'approved' if approved else 'rejected'} the action.")

                env = await gate.ask_choice(
                    "Which environment?",
                    choices=["development", "staging", "production"]
                )
                await gate.notify(f"Selected: {env}")
            except TimeoutError as e:
                print(f"Demo timed out: {e}")
        else:
            # Run agent task with human gate injected
            from gws_assistant.agent_system import WorkspaceAgentSystem as AgentSystem
            from gws_assistant.config import AppConfig

            config = AppConfig.from_env()
            logger = logging.getLogger("agent")

            agent = AgentSystem(config=config, logger=logger)
            # Inject human gate. Note: Requires AgentSystem to use it,
            # this is a stub for the integration point.
            agent.human_gate = gate

            result = await agent.run(args.task)
            await gate.notify(f"✅ Task completed:\n{result}")
    finally:
        await gate.stop()

if __name__ == "__main__":
    asyncio.run(main())
