# code/__init__.py
# Convenience re-exports from submodules
from .pose_analyzer import (
    PoseAnalyzer, JointAngles, TemporalFeatures, ExerciseStandard,
    ErrorInfo, ScoreResult, AnalysisResult, EXERCISE_STANDARDS,
    calculate_angle, calculate_vertical_angle, valid_point,
)
from .visualization import JointAngleHeatmap, generate_ascii_heatmap, STANDARD_REFERENCE_ANGLES

# ---------------------------------------------------------------------------
# Fix: the project's `code/` package shadows Python's stdlib `code` module.
# torch.distributed → pdb → code.InteractiveConsole crashes without this.
# We load the stdlib module from its file path and re-export the key attribute.
# ---------------------------------------------------------------------------
import os as _os
import importlib.machinery as _machinery
import importlib.util as _util

_stdlib_path = _os.path.join(_os.path.dirname(_os.__file__), 'code.py')
if _os.path.exists(_stdlib_path):
    _loader = _machinery.SourceFileLoader('_stdlib_code', _stdlib_path)
    _spec = _util.spec_from_loader('_stdlib_code', _loader)
    _stdlib = _util.module_from_spec(_spec)
    _loader.exec_module(_stdlib)
    # Re-export the attributes that pdb (and others) expect
    InteractiveConsole = _stdlib.InteractiveConsole
    InteractiveInterpreter = _stdlib.InteractiveInterpreter
    compile_command = _stdlib.compile_command
    interact = _stdlib.interact
