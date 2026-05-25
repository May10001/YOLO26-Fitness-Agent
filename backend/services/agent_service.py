import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

_agent = None


def get_agent():
    global _agent
    if _agent is None:
        from code.agent import FitnessAgent
        _agent = FitnessAgent(model_size="0.5B")
    return _agent
