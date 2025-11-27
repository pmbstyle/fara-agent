"""Simplified Fara Agent for LM Studio"""
import asyncio
import json
import logging
import io
from typing import List, Dict, Any, Optional
from PIL import Image
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from browser import SimpleBrowser
from message_types import SystemMessage, UserMessage, AssistantMessage, ImageObj, message_to_openai_format
from prompts import get_computer_use_system_prompt
from utils import get_trimmed_url


class FaraAgent:
    """Simplified Fara agent optimized for LM Studio"""
    
    MLM_PROCESSOR_IM_CFG = {
        "min_pixels": 3136,
        "max_pixels": 12845056,
        "patch_size": 14,
        "merge_size": 2,
    }
    
    def __init__(
        self,
        config: Dict[str, Any],
        headless: bool = True,
        logger: Optional[logging.Logger] = None,
        on_update: Optional[Any] = None
    ):
        self.config = config
        self.headless = headless
        self.logger = logger or logging.getLogger("fara_agent")
        self.on_update = on_update
        self.viewport_width = 1440
        self.viewport_height = 900
        self.last_im_size: tuple[int, int] | None = None
        self.facts: list[str] = []
        self.max_n_images = config.get("max_n_images", 1)
        self.downloads_folder = config.get("downloads_folder")
        self.message_history: list[UserMessage] = []
        self.show_overlay = config.get("show_overlay", not headless)
        self.show_click_markers = config.get("show_click_markers", not headless)
        
        self.browser = SimpleBrowser(
            headless=headless,
            viewport_width=self.viewport_width,
            viewport_height=self.viewport_height,
            downloads_folder=self.downloads_folder,
            show_overlay=self.show_overlay,
            show_click_markers=self.show_click_markers,
            logger=self.logger
        )
        
        self.client = AsyncOpenAI(
            api_key=config.get("api_key", "lm-studio"),
            base_url=config.get("base_url", "http://localhost:1234/v1")
        )
        
        self.history: List[Any] = []
        self.max_rounds = config.get("max_rounds", 15)
        self.save_screenshots = config.get("save_screenshots", True)
        self.screenshots_folder = config.get("screenshots_folder", "./screenshots")
        self.round_count = 0
        self._is_lm_studio = "1234" in str(config.get("base_url", "")) or "lm-studio" in str(config.get("api_key", ""))
        self.scroll_history: list[dict[str, Any]] = []
        self._stopping = False
    
    async def start(self):
        """Initialize the agent"""
        self._stopping = False
        await self.browser.start()
        self.logger.info("Agent started")
    
    def stop(self):
        """Signal the agent to stop"""
        self._stopping = True
        self.logger.info("Agent stopping...")

    async def close(self):
        """Close the agent"""
        await self.browser.close()
        self.logger.info("Agent closed")
    
    async def _get_screenshot(self) -> Image.Image:
        """Capture and return screenshot as PIL Image"""
        screenshot_bytes = await self.browser.screenshot()
        return Image.open(io.BytesIO(screenshot_bytes))
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2.0, min=2.0, max=10),
        reraise=True,
    )
    async def _call_model(self, messages: List[Any]) -> str:
        """Call the LLM with retry logic"""
        openai_messages = [message_to_openai_format(msg) for msg in messages]
        create_kwargs = {
            "model": self.config.get("model", "microsoft_fara-7b"),
            "messages": openai_messages,
            "temperature": self.config.get("temperature", 0.0),
            "max_tokens": 1024,
            "stop": ["</tool_call>", "<|im_end|>", "<|endoftext|>"],
        }
        if self._is_lm_studio:
            create_kwargs["top_p"] = 0.95
        response = await self.client.chat.completions.create(**create_kwargs)
        
        return response.choices[0].message.content
    
    def _parse_action(self, response: str) -> Dict[str, Any] | None:
        """Parse tool call from model response"""
        if "<tool_call>" not in response:
            return None
        
        try:
            # Extract JSON between <tool_call> tags
            start = response.find("<tool_call>") + len("<tool_call>")
            end = response.find("</tool_call>", start)
            if end == -1:
                end = len(response)
            
            json_str = response[start:end].strip()
            tool_call = json.loads(json_str)
            
            if tool_call.get("name") == "computer_use":
                return tool_call.get("arguments", {})
        except Exception as e:
            self.logger.error(f"Failed to parse action: {e}")
        
        return None
    
    def _convert_resized_coords_to_viewport(self, coords: List[float]) -> List[float]:
        """Scale coordinates from resized prompt image back to browser viewport."""
        if not self.last_im_size:
            return coords
        im_w, im_h = self.last_im_size
        scale_x = self.viewport_width / im_w
        scale_y = self.viewport_height / im_h
        return [coords[0] * scale_x, coords[1] * scale_y]
    
    def _normalize_url_or_search(self, raw: str) -> str:
        """Return a URL, performing search fallback when the input isn't a full URL."""
        if raw.startswith(("https://", "http://", "file://", "about:")):
            return raw
        if " " in raw:
            return f"https://www.bing.com/search?q={raw}"
        return f"https://{raw}"

    def _prune_user_messages(self) -> list[UserMessage]:
        """Keep only the latest user messages up to max_n_images images."""
        if self.max_n_images <= 0:
            return []
        kept: list[UserMessage] = []
        images_seen = 0
        for msg in reversed(self.message_history):
            has_image = any(isinstance(item, ImageObj) for item in msg.content) if isinstance(msg.content, list) else False
            if has_image:
                if images_seen >= self.max_n_images:
                    continue
                images_seen += 1
            kept.append(msg)
        return list(reversed(kept))
    
    async def _execute_action(self, action_args: Dict[str, Any]) -> str:
        """Execute a browser action"""
        action = action_args.get("action")
        if action == "click":
            action = "left_click"
        if action == "input_text":
            action = "type"
        
        try:
            if action == "visit_url":
                url = action_args.get("url")
                if not url:
                    return "No URL provided."
                target = self._normalize_url_or_search(str(url))
                await self.browser.goto(target)
                return f"I typed '{url}' into the browser address bar."
            
            elif action == "left_click":
                coord = action_args.get("coordinate", [0, 0])
                scaled = self._convert_resized_coords_to_viewport(coord)
                await self.browser.click(scaled[0], scaled[1])
                if self.show_click_markers:
                    await self.browser.show_click_marker(scaled[0], scaled[1], "click")
                return f"I clicked at coordinates ({scaled[0]:.1f}, {scaled[1]:.1f})."
            
            elif action in ("mouse_move", "hover"):
                coord = action_args.get("coordinate", [0, 0])
                scaled = self._convert_resized_coords_to_viewport(coord)
                await self.browser.hover(scaled[0], scaled[1])
                if self.show_click_markers:
                    await self.browser.show_click_marker(scaled[0], scaled[1], "hover")
                return f"I moved the cursor to ({scaled[0]:.1f}, {scaled[1]:.1f})."
            
            elif action == "type":
                coord = action_args.get("coordinate")
                text = action_args.get("text", "")
                press_enter = action_args.get("press_enter", False)
                delete_existing_text = action_args.get("delete_existing_text", False)
                
                if coord:
                    scaled = self._convert_resized_coords_to_viewport(coord)
                    await self.browser.click(scaled[0], scaled[1])
                    if self.show_click_markers:
                        await self.browser.show_click_marker(scaled[0], scaled[1], "type")
                    await asyncio.sleep(0.2)
                
                await self.browser.type_text(text, press_enter, delete_existing_text)
                return f"I typed '{text}'."
            
            elif action == "scroll":
                pixels = action_args.get("pixels", 0)
                direction = "up" if pixels > 0 else "down"
                if pixels > 0:
                    await self.browser.page_up()
                elif pixels < 0:
                    await self.browser.page_down()
                else:
                    await self.browser.scroll(pixels)
                # Record scroll context to help the model avoid loops
                scroll_state = await self.browser.get_scroll_position()
                self.scroll_history.append({
                    "direction": direction,
                    "y": scroll_state.get("y", 0),
                    "scrollHeight": scroll_state.get("scrollHeight", 0),
                    "timestamp": asyncio.get_event_loop().time(),
                })
                return f"I scrolled {direction} one page in the browser."
            
            elif action in ("key", "keypress"):
                keys = action_args.get("keys", [])
                if not keys:
                    return "No keys provided."
                for key in keys:
                    await self.browser.press_key(key)
                return f"I pressed keys: {', '.join(keys)}."
            
            elif action == "history_back":
                await self.browser.go_back()
                return "I went back to the previous page."
            
            elif action == "web_search":
                query = action_args.get("query", "")
                # Use Bing search
                search_url = f"https://www.bing.com/search?q={query}"
                await self.browser.goto(search_url)
                return f"I typed '{query}' into the browser search bar."
            
            elif action == "wait":
                time_secs = action_args.get("time", action_args.get("duration", 1)) or 1
                await asyncio.sleep(time_secs)
                return f"I waited for {time_secs} seconds."
            
            elif action == "pause_and_memorize_fact":
                fact = action_args.get("fact") or ""
                if fact:
                    self.facts.append(str(fact))
                return "I paused to memorize a fact."
            
            elif action == "terminate":
                status = action_args.get("status", "success")
                if self.facts:
                    return f"Task completed with status: {status}. Memorized facts: {self.facts}"
                return f"Task completed with status: {status}"
            
            else:
                return f"Unknown action: {action}"
        
        except Exception as e:
            self.logger.error(f"Action execution failed: {e}")
            return f"Action failed: {str(e)}"
    
    async def run(self, task: str):
        """Run the agent on a task"""
        self.logger.info(f"Running task: {task}")
        
        # Get initial screenshot and create system prompt
        screenshot = await self._get_screenshot()
        if self.on_update:
            if asyncio.iscoroutinefunction(self.on_update):
                await self.on_update({"type": "screenshot", "image": screenshot})
            else:
                self.on_update({"type": "screenshot", "image": screenshot})

        prompt_data = get_computer_use_system_prompt(screenshot, self.MLM_PROCESSOR_IM_CFG)
        
        # Initialize history with system prompt
        system_prompt = SystemMessage(content=prompt_data["content"])
        
        # Track action history for context (text only)
        action_history = []
        
        # Main loop
        for round_num in range(self.max_rounds):
            if self._stopping:
                self.logger.info("Agent stopped by user request")
                break

            self.round_count = round_num + 1
            self.logger.info(f"Round {self.round_count}/{self.max_rounds}")
            
            # Build context summary from recent actions
            context_text = f"Task: {task}\n\nCurrent URL: {self.browser.get_url()}"
            if action_history:
                recent_actions = action_history[-3:]  # Last 3 actions
                context_text += "\n\nRecent actions:\n" + "\n".join(recent_actions)
            # Add scroll position info to reduce oscillation
            if self.scroll_history:
                last_scroll = self.scroll_history[-1]
                sh = last_scroll.get("scrollHeight", 0) or 1
                y = last_scroll.get("y", 0)
                pct = (y / sh) * 100
                context_text += f"\n\nScroll position: {y:.0f}/{sh:.0f} ({pct:.1f}%)."
                # Detect oscillating scrolls and warn model
                recent_dirs = [s["direction"] for s in self.scroll_history[-6:]]
                if "up" in recent_dirs and "down" in recent_dirs and len(recent_dirs) >= 4:
                    context_text += "\n\nLoop warning: You have been scrolling up/down repeatedly. Avoid more scrolling; prefer clicking a result or using the search bar."
            context_text += "\n\nWhat should I do next? If the task is complete, use the 'terminate' action with status 'success'."
            
            # Create user message with screenshot and context
            user_content = [
                ImageObj.from_pil(screenshot.resize(prompt_data["im_size"])),
                context_text
            ]
            self.last_im_size = prompt_data["im_size"]
            user_message = UserMessage(content=user_content)
            self.message_history.append(user_message)
            pruned_users = self._prune_user_messages()
            
            # Call model with system prompt + current state only (LM Studio single-image mode)
            messages_for_model = [system_prompt, *pruned_users]
            
            response = await self._call_model(messages_for_model)
            self.logger.info(f"Model response: {response[:200]}...")

            if self.on_update:
                update_data = {"type": "model_response", "content": response}
                if asyncio.iscoroutinefunction(self.on_update):
                    await self.on_update(update_data)
                else:
                    self.on_update(update_data)

            # Update debug overlay for headful runs without affecting screenshots
            if self.show_overlay:
                await self.browser.update_overlay(f"[INFO] Model response: {response}")
            
            # Parse action
            action_args = self._parse_action(response)
            
            if not action_args:
                self.logger.warning("No valid action found in response")
                break
            
            # Check for termination
            if action_args.get("action") == "terminate":
                self.logger.info(f"Task terminated: {action_args.get('status')}")
                break
            
            # Execute action
            result = await self._execute_action(action_args)
            self.logger.info(f"Action result: {result}")
            
            if self.on_update:
                update_data = {"type": "action_result", "content": result, "action": action_args}
                if asyncio.iscoroutinefunction(self.on_update):
                    await self.on_update(update_data)
                else:
                    self.on_update(update_data)

            # Add to action history
            action_summary = f"{round_num+1}. {action_args.get('action')}: {result}"
            action_history.append(action_summary)
            
            # Get new screenshot
            await asyncio.sleep(1.5)  # Wait for page to update
            screenshot = await self._get_screenshot()
            
            if self.on_update:
                if asyncio.iscoroutinefunction(self.on_update):
                    await self.on_update({"type": "screenshot", "image": screenshot})
                else:
                    self.on_update({"type": "screenshot", "image": screenshot})

            # Save screenshot if enabled
            if self.save_screenshots:
                import os
                os.makedirs(self.screenshots_folder, exist_ok=True)
                screenshot.save(f"{self.screenshots_folder}/screenshot{round_num}.png")
            
            # Update prompt data for new screenshot
            prompt_data = get_computer_use_system_prompt(screenshot, self.MLM_PROCESSOR_IM_CFG)
        
        self.logger.info(f"Task completed after {self.round_count} rounds")

