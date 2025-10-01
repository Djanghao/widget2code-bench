# Widget2Code Baselines

Batch inference tool for widget-to-code generation using LLMs.

## Usage

```bash
source venv/bin/activate
python scripts/batch_infer.py \
  --images-dir <path> \
  --prompts-root <path> \
  --results-root <path> \
  --experiment <name> \
  [options]
```

## Required Arguments

- `--images-dir`: Directory containing input images
- `--prompts-root`: Directory containing prompt markdown files
- `--results-root`: Directory for output results
- `--experiment`: Experiment name

## Optional Arguments

- `--threads <N>`: Concurrent workers (default: CPU count)
- `--model <name>`: Model ID (default: doubao-seed-1-6-250615)
- `--temperature <float>`: Temperature (default: 0.2)
- `--top-p <float>`: Top-p (default: 0.9)
- `--max-tokens <int>`: Max tokens (default: 1500)
- `--timeout <int>`: Timeout in seconds (default: 90)
- `--thinking`: Enable provider thinking
- `--include <pattern>`: Filter prompts (e.g., "html/*")
- `--exclude <pattern>`: Exclude prompts
- `--suffix <str>`: Extra suffix for run directory
- `--size`: Append image size constraint to prompt
- `--aspect-ratio`: Append aspect ratio constraint to prompt

## Examples

Basic usage:
```bash
python scripts/batch_infer.py \
  --images-dir ./images \
  --prompts-root ./prompts \
  --results-root ./results \
  --experiment my-test
```

With size constraints:
```bash
python scripts/batch_infer.py \
  --images-dir ./images \
  --prompts-root ./prompts \
  --results-root ./results \
  --experiment test-size \
  --size
```

With aspect ratio constraints:
```bash
python scripts/batch_infer.py \
  --images-dir ./images \
  --prompts-root ./prompts \
  --results-root ./results \
  --experiment test-aspect \
  --aspect-ratio
```

With both size and aspect ratio:
```bash
python scripts/batch_infer.py \
  --images-dir ./images \
  --prompts-root ./prompts \
  --results-root ./results \
  --experiment test-both \
  --size --aspect-ratio
```

Filter specific prompts:
```bash
python scripts/batch_infer.py \
  --images-dir ./images \
  --prompts-root ./prompts \
  --results-root ./results \
  --experiment html-only \
  --include "html/*"
```

## Output Structure

```
results/
└── <timestamp>-<experiment>/
    ├── run.meta.json
    └── <image_id>/
        ├── source.png
        └── <category>/
            ├── <prompt_name>.html
            └── <prompt_name>.meta.json
```

Each `<prompt_name>.meta.json` contains:
- `prompt`: Full prompt text used
- `category`: Prompt category
- `prompt_file`: Source prompt file
- `size_flag`: Whether --size was used
- `aspect_ratio_flag`: Whether --aspect-ratio was used
- `image_size`: Image dimensions (if flags enabled)
- `aspect_ratio`: Image aspect ratio (if flags enabled)
