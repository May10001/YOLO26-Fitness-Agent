# 服务器微调操作指南

## 一、需要传输的文件

项目中有大量不需要的文件（GUI 应用、爬虫、模型对比报告等），以下是最小传输集合：

### 方案 A：直接使用已生成的数据集（推荐）

```
远程服务器目录结构：
~/fitness-finetune/
├── code/
│   ├── __init__.py
│   └── models/
│       ├── __init__.py
│       ├── base_model.py              # 微调后推理用
│       ├── fitness_assistant.py       # 微调后推理用
│       └── fine_tuning/
│           ├── __init__.py
│           ├── trainer.py             # ★ 微调主脚本
│           ├── prepare_data.py        # 数据格式转换
│           └── fitness_data.py        # 内置小数据集（回退用）
├── data/
│   └── processed/
│       └── fitness_dataset.jsonl      # ★ 1626条已生成的数据集
└── requirements.txt                   # 依赖
```

**传输命令**（在本地项目根目录执行）：

```bash
# 在服务器上创建目录
ssh user@your-server "mkdir -p ~/fitness-finetune/code/models/fine_tuning ~/fitness-finetune/data/processed"

# 传输文件
scp code/__init__.py user@your-server:~/fitness-finetune/code/
scp code/models/__init__.py user@your-server:~/fitness-finetune/code/models/
scp code/models/base_model.py user@your-server:~/fitness-finetune/code/models/
scp code/models/fitness_assistant.py user@your-server:~/fitness-finetune/code/models/
scp code/models/fine_tuning/*.py user@your-server:~/fitness-finetune/code/models/fine_tuning/
scp data/processed/fitness_dataset.jsonl user@your-server:~/fitness-finetune/data/processed/
scp requirements.txt user@your-server:~/fitness-finetune/
```

### 方案 B：在服务器上重新生成数据集

如果要在服务器上从头生成数据集，额外传输：

```bash
# 在服务器上创建目录
ssh user@your-server "mkdir -p ~/fitness-finetune/code/{data_collection,data_processing,prompt_engineering}"

# 额外传输数据处理管线
scp code/data_processing/*.py user@your-server:~/fitness-finetune/code/data_processing/
scp code/data_collection/*.py user@your-server:~/fitness-finetune/code/data_collection/
```

推荐方案 A，因为数据集已经在本机生成好，直接传 JSONL 最省事。

***

## 二、服务器环境配置

### 2.1 登录服务器

```bash
ssh user@your-server-ip
```

### 2.2 安装 CUDA 版 PyTorch

```bash
# 确认 GPU 可用
nvidia-smi

# 根据 CUDA 版本安装 PyTorch（以下为 CUDA 12.1 示例）
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### 2.3 安装其余依赖

```bash
cd ~/fitness-finetune
pip install -r requirements.txt
pip install peft trl datasets bitsandbytes accelerate
```

如果 `bitsandbytes` 安装失败（某些服务器架构不兼容），安装 JIT 版本：

```bash
pip install bitsandbytes --prefer-binary
```

### 2.4 验证环境

```bash
python -c "
import torch
print(f'PyTorch: {torch.__version__}')
print(f'CUDA available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'GPU: {torch.cuda.get_device_name(0)}')
    print(f'VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB')
"
```

***

## 三、选择模型规格

根据服务器 GPU 显存选择：

| GPU              | 显存       | 推荐模型   | 加载方式       | 命令                           |
| ---------------- | -------- | ------ | ---------- | ---------------------------- |
| RTX 3060 / A4000 | 12GB     | 1.5B   | QLoRA int4 | `--model 1.5B`               |
| RTX 4060         | 8GB      | 1.5B   | QLoRA int4 | `--model 1.5B`               |
| RTX 4070 / 3080  | 10-12GB  | 3B     | QLoRA int4 | `--model 3B`                 |
| RTX 4090 / A5000 | 24GB     | 7B     | bf16       | `--model 7B`                 |
| **RTX 5090**     | **32GB** | **7B** | **bf16**   | `--model 7B --batch-size 8`  |
| A100 / H100      | 40-80GB  | 7B     | bf16       | `--model 7B --batch-size 16` |

> RTX 5090 有 32GB 显存 + bf16 支持，直接跑 7B 全精度训练，不需要 QLoRA，忽略 bitsandbytes 的警告信息（那个只是检测库是否存在，实际不会用到）。

***

## 四、开始微调

### 4.1 使用 tmux 保持会话

微调可能持续数十分钟到数小时，必须用 tmux/screen 防止 SSH 断开导致中断：

```bash
# 创建新会话
tmux new -s finetune

# 进入项目目录
cd ~/fitness-finetune

# 如果断开后重连
tmux attach -t finetune
```

### 4.2 转换数据格式（必须先执行）

```bash
python -m code.models.fine_tuning.prepare_data
```

预期输出（纯文本处理，不加载模型，几秒钟完成）：

```
INFO - Loading dataset: data/processed/fitness_dataset.jsonl
INFO - Loaded 1626 raw samples
INFO - Converted 1626 samples, skipped 0
INFO - Train: 1464 → data/processed/training_data.jsonl
INFO - Eval:  162 → data/processed/eval_data.jsonl
```

### 4.3 快速测试（验证环境）

用 0.5B 模型 + 内置小数据集跑 1 epoch，约 3 分钟，验证环境无误：

```bash
python -m code.models.fine_tuning.trainer \
    --model 0.5B \
    --use-builtin-data \
    --epochs 1 \
    --batch-size 2
```

看到 `Fine-tuning complete!` 即环境正常。如果中途报错退出，根据错误信息排查（常见问题见第六章）。

### 4.4 正式微调

```bash
# RTX 5090 (32GB)：直接用 7B + bf16，最佳质量
HF_ENDPOINT=https://hf-mirror.com \
HF_HOME=/dev/shm \
python -u -m code.models.fine_tuning.trainer \
    --model 7B \
    --epochs 3 \
    --batch-size 8

# 一般 GPU：1.5B + QLoRA，稳妥可靠
python -m code.models.fine_tuning.trainer \
    --model 1.5B \
    --epochs 3 \
    --batch-size 2
```

### 4.5 预计耗时

| 模型     | GPU          | 数据集         | 加载方式     | 预计时间         |
| ------ | ------------ | ----------- | -------- | ------------ |
| 0.5B   | RTX 4060     | 内置55条       | QLoRA    | \~3 min      |
| 0.5B   | RTX 4060     | 完整1464条     | QLoRA    | \~10 min     |
| 1.5B   | RTX 4060     | 完整1464条     | QLoRA    | \~25 min     |
| 3B     | RTX 4090     | 完整1464条     | bf16     | \~25 min     |
| 7B     | RTX 4090     | 完整1464条     | QLoRA    | \~90 min     |
| **7B** | **RTX 5090** | **完整1464条** | **bf16** | **\~35 min** |
| 0.5B   | CPU          | 完整1464条     | fp32     | 数小时          |

***

## 五、微调完成后

### 5.1 确认产出

```bash
ls -la ~/fitness-finetune/lora_fitness_adapter/
# 应该看到类似:
# 1.5B_20260517_120000/
#   ├── adapter/              ← 这是要用的
#   ├── checkpoint-100/
#   └── checkpoint-200/
```

### 5.2 快速验证微调效果

```bash
python -c "
from pathlib import Path
import sys
sys.path.insert(0, str(Path.cwd()))

from code.models.base_model import BaseModel

# 加载微调后的模型
adapter = list(Path('lora_fitness_adapter').rglob('adapter'))[0]
model = BaseModel.get_instance(lora_path=str(adapter), model_size='0.5B')

# 测试
reply = model.chat([
    {'role': 'system', 'content': '你是一名专业的健身教练和运动科学顾问。请用中文回答。'},
    {'role': 'user', 'content': '深蹲时膝盖内扣怎么办？请给出具体的纠正建议。'},
])
print(reply)
"
```

### 5.3 下载 LoRA adapter 回本地

```bash
# 在本地执行
scp -r user@your-server:~/fitness-finetune/lora_fitness_adapter ./
```

然后在本地使用：

```python
from code.models.fitness_assistant import FitnessAssistant

assistant = FitnessAssistant(
    lora_path="./lora_fitness_adapter/1.5B_20260517_120000/adapter",
    model_size="1.5B",
)
reply = assistant.chat("俯卧撑时肩膀疼是怎么回事？")
print(reply)
```

***

## 六、常见问题

### Q: 报错 `evaluation_strategy` 参数不存在？

```
TypeError: TrainingArguments.__init__() got an unexpected keyword argument 'evaluation_strategy'
```

新版 transformers（4.46+）将此参数改名为 `eval_strategy`。已修复，重新传 `trainer.py` 到服务器即可。

### Q: 出现 `bitsandbytes library load error` 警告？

```
ERROR: Configured CUDA binary not found at .../libbitsandbytes_cuda132.so
```

这是 bitsandbytes 库检测到 CUDA 13.2（RTX 5090 的 CUDA 版本）但没有预编译的二进制文件。**如果你的 GPU 显存 ≥18GB，忽略此警告即可**——训练器会自动使用 bf16/fp16 而非 QLoRA，根本不调用 bitsandbytes。

如果确实需要 QLoRA（显存 <12GB），从源码编译：

```bash
git clone https://github.com/TimDettmers/bitsandbytes.git
cd bitsandbytes
CUDA_VERSION=132 make cuda12x
python setup.py install
```

### Q: bitsandbytes 安装失败？

```bash
# 尝试预编译版本
pip install bitsandbytes --prefer-binary

# 或者从源码编译（需要 CUDA Toolkit）
git clone https://github.com/TimDettmers/bitsandbytes.git
cd bitsandbytes
CUDA_VERSION=121 make cuda12x
python setup.py install
```

### Q: CUDA out of memory (OOM)？

减小 batch size 或换更小的模型：

```bash
python -m code.models.fine_tuning.trainer --model 1.5B --batch-size 1
```

### Q: 训练中断了怎么恢复？

```bash
python -m code.models.fine_tuning.trainer \
    --model 1.5B \
    --resume lora_fitness_adapter/1.5B_xxx/checkpoint-200
```

### Q: 服务器上没有 `code/data_collection` 也能跑吗？

可以。`prepare_data.py` 直接读已生成的 `fitness_dataset.jsonl`，不依赖爬虫模块。

### Q: 如何监控 GPU 使用？

另开一个终端：

```bash
watch -n 1 nvidia-smi
```

或在 tmux 内分屏：

```bash
# Ctrl+b 然后按 %   （左右分屏）
# 在另一边运行 watch nvidia-smi
```

