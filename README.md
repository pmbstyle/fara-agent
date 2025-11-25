# Fara Standalone Agent

A minimal, standalone version of the Fara-7B web agent optimized for LM Studio inference.

## Features

- ✅ Completely self-contained (no external dependencies)
- ✅ Optimized for LM Studio with single-image mode
- ✅ Simple browser automation via Playwright

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
playwright install firefox
```

### 2. Setup LM Studio

1. Download and install [LM Studio](https://lmstudio.ai/)
2. Download the [Fara-7B](https://huggingface.co/bartowski/microsoft_Fara-7B-GGUF) model (GGUF format):
   - Search for: `microsoft_fara-7b`
   - Recommended: Q5_K_M quantization (6GB)
3. Load the model in LM Studio
4. Start the local server (default port: 1234)
5. In model settings:
   - Context Length: 8192+
   - Temperature: 0.0
   - Top P: 0.9

### 3. Run the Agent

```bash
python run_agent.py --task "Go to wikipedia.org and search for cats" --headful
```

Optional debug flags (enabled by default in headful mode):
- `show_overlay`: bottom-right HUD with latest model responses (hidden during screenshots)
- `show_click_markers`: transient markers for clicks/hover/type coordinates (hidden during screenshots)

## Configuration

Edit `config.json` to change:
- Model endpoint (default: http://localhost:1234/v1)
- Model name
- Max rounds
- Screenshot settings
- Max images to keep in context (`max_n_images`, default 1)
- Downloads folder for saving files
- Debug overlay and click markers (`show_overlay`, `show_click_markers`)

## How It Works

1. **Browser Control**: Uses Playwright to control Firefox
2. **Vision**: Takes screenshots and sends them to the model
3. **Actions**: Model returns tool calls (click, type, scroll, navigate, hover, keypress, wait, memorize facts)
4. **Single-Image Mode**: Only sends the latest screenshot to LM Studio (better compatibility)
5. **Loop Guard**: Tracks scroll position and warns the model when it oscillates up/down

## Limitations

- Quantized models have reduced capabilities vs full model
- LM Studio has issues with multiple images in conversation history
- Some complex tasks may cause loops (scrolling, navigation)

## Troubleshooting

**Browser not visible?**
- Make sure you're using `--headful` flag

**Model not responding?**
- Check LM Studio server is running on port 1234
- Verify model is loaded in LM Studio

**Agent looping?**
- Try reducing temperature in LM Studio to 0.0
- Reduce `max_rounds` in config.json

## License

MIT License - Based on [Microsoft Fara-7B](https://www.microsoft.com/en-us/research/blog/fara-7b-an-efficient-agentic-model-for-computer-use/)

