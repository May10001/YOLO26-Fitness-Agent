"""
FitnessAgent -- Main orchestrator tying models + guidance + planning.

Provides a unified interface for:
  - chat(message)        → delegates to dialogue or fitness assistant
  - get_guidance(result) → delegates to context engine
  - generate_plan()      → delegates to plan generator
  - start_fine_tuning()  → delegates to trainer
"""

import logging
from pathlib import Path
from typing import Optional

from .pose_analyzer import AnalysisResult
from .models.dialogue_assistant import DialogueAssistant
from .models.fitness_assistant import FitnessAssistant
from .guidance.context_engine import ContextEngine, GuidanceMessage
from .planning.user_profile import UserProfile
from .planning.plan_generator import PlanGenerator

logger = logging.getLogger(__name__)

FITNESS_KEYWORDS = [
    "健身", "锻炼", "训练", "运动", "深蹲", "俯卧撑", "平板支撑",
    "卷腹", "开合跳", "肌肉", "减脂", "增肌", "瘦", "胖", "体重",
    "蛋白", "饮食", "营养", "卡路里", "热量", "有氧", "无氧",
    "动作", "姿势", "纠正", "错误", "膝盖", "腰", "背", "肩",
    "拉伸", "热身", "恢复", "休息", "计划", "教练", "指导",
    "出汗", "心率", "组数", "次数", "间歇", "力竭", "酸痛",
    "受伤", "损伤", "疼痛", "康复", "腹肌", "臀", "胸肌",
    "臂", "腿", "核心", "HIIT", "有氧运动", "力量训练",
    "减肥", "塑形", "瑜伽", "普拉提", "跑步", "游泳",
    "骑行", "跳绳", "哑铃", "杠铃", "弹力带", "自重",
]


class FitnessAgent:
    """Main orchestrator for the YOLO26 fitness AI assistant.

    Usage:
        agent = FitnessAgent()
        agent.set_exercise("深蹲")
        agent.set_user_profile(user)

        guidance = agent.get_guidance(analysis_result)  # per-frame
        reply = agent.chat("深蹲时膝盖能不能超过脚尖？")  # chat
        plan = agent.generate_plan()  # workout plan
    """

    def __init__(
        self,
        lora_path: Optional[str] = None,
        profile_dir: Path = Path("./user_profiles"),
    ):
        self.lora_path = lora_path
        self.profile_dir = Path(profile_dir)

        self._dialogue: Optional[DialogueAssistant] = None
        self._fitness: Optional[FitnessAssistant] = None
        self._guidance_engine: Optional[ContextEngine] = None
        self._profile: Optional[UserProfile] = None
        self._exercise_name: str = "深蹲"

    # ---- Model accessors (lazy init) ----

    @property
    def dialogue(self) -> DialogueAssistant:
        if self._dialogue is None:
            logger.info("Initializing DialogueAssistant")
            self._dialogue = DialogueAssistant()
        return self._dialogue

    @property
    def fitness(self) -> FitnessAssistant:
        if self._fitness is None:
            logger.info("Initializing FitnessAssistant (lora=%s)", self.lora_path)
            self._fitness = FitnessAssistant(lora_path=self.lora_path)
        return self._fitness

    # ---- Exercise management ----

    def set_exercise(self, exercise_name: str):
        """Switch current exercise and reset guidance engine."""
        self._exercise_name = exercise_name
        self._guidance_engine = ContextEngine(exercise_name)

    # ---- User profile ----

    def set_user_profile(self, profile: UserProfile):
        self._profile = profile

    def load_user_profile(self, name: str) -> UserProfile:
        profile = UserProfile.load(name, self.profile_dir)
        self._profile = profile
        return profile

    def save_user_profile(self):
        if self._profile is not None:
            self._profile.save(self.profile_dir)

    @property
    def profile(self) -> UserProfile:
        if self._profile is None:
            self._profile = UserProfile()
        return self._profile

    # ---- Intent classification ----

    def _is_fitness_query(self, message: str) -> bool:
        for kw in FITNESS_KEYWORDS:
            if kw in message:
                return True
        return False

    # ---- Chat ----

    def chat(
        self,
        message: str,
        pose_context: Optional[str] = None,
        max_tokens: int = 512,
    ) -> str:
        """Respond to a user message. Auto-routes to correct assistant."""
        is_fitness = self._is_fitness_query(message)

        if is_fitness:
            if pose_context is None and self._guidance_engine is not None:
                pose_context = self._guidance_engine.get_summary_context()
            return self.fitness.chat(
                message,
                pose_context=pose_context,
                max_tokens=max_tokens,
            )
        else:
            return self.dialogue.chat(
                message,
                max_tokens=max_tokens,
            )

    # ---- Guidance ----

    def get_guidance(self, result: AnalysisResult) -> Optional[GuidanceMessage]:
        """Get real-time coaching guidance from a pose analysis result."""
        if self._guidance_engine is None:
            self._guidance_engine = ContextEngine(self._exercise_name)
        return self._guidance_engine.process(result)

    def get_guidance_text(self, result: AnalysisResult) -> Optional[str]:
        msg = self.get_guidance(result)
        return msg.text if msg else None

    # ---- Planning ----

    def generate_plan(self) -> Optional[str]:
        """Generate a weekly workout plan based on user profile."""
        if self._profile is None:
            self._profile = UserProfile()
        generator = PlanGenerator(self._profile)
        plan = generator.generate_weekly_plan()
        return plan.to_text()

    # ---- Training ----

    def start_fine_tuning(
        self,
        output_dir: Path = Path("./lora_fitness_adapter"),
        num_epochs: int = 3,
    ) -> Path:
        """Run LoRA fine-tuning and return adapter path."""
        from .models.fine_tuning.trainer import fine_tune

        logger.info("Starting fine-tuning...")
        adapter_path = fine_tune(
            output_dir=output_dir,
            num_epochs=num_epochs,
        )
        self.lora_path = str(adapter_path)
        logger.info("Fine-tuning complete. Adapter: %s", adapter_path)
        return adapter_path
