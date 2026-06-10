# Lazy imports: avoid loading torch/transformers when only using prepare_data.
# Heavy imports (trainer, fitness_data) are deferred until accessed.

def __getattr__(name):
    if name in ("fine_tune", "MODEL_REGISTRY", "DEFAULT_MODEL"):
        from .trainer import fine_tune, MODEL_REGISTRY, DEFAULT_MODEL
        globals()[name] = fine_tune if name == "fine_tune" else (
            MODEL_REGISTRY if name == "MODEL_REGISTRY" else DEFAULT_MODEL
        )
        return globals()[name]
    if name in ("get_fitness_dataset", "ALL_CONVERSATIONS"):
        from .fitness_data import get_fitness_dataset, ALL_CONVERSATIONS
        globals()[name] = get_fitness_dataset if name == "get_fitness_dataset" else ALL_CONVERSATIONS
        return globals()[name]
    if name in ("prepare_training_data", "convert_sample"):
        from .prepare_data import prepare_training_data, convert_sample
        globals()[name] = prepare_training_data if name == "prepare_training_data" else convert_sample
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
