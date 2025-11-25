"""Simplified browser controller for Fara agent"""
import asyncio
import logging
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page


class SimpleBrowser:
    """Simplified browser manager using Playwright"""
    
    def __init__(
        self,
        headless: bool = True,
        viewport_width: int = 1440,
        viewport_height: int = 900,
        downloads_folder: str | None = None,
        show_overlay: bool = False,
        show_click_markers: bool = False,
        logger: Optional[logging.Logger] = None
    ):
        self.headless = headless
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self.logger = logger or logging.getLogger("browser")
        self.downloads_folder = downloads_folder
        self.show_overlay = show_overlay
        self.show_click_markers = show_click_markers
        self._overlay_created = False
        self._marker_created = False
        self._last_overlay_text: str | None = None
        
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.last_download_path: str | None = None
    
    async def start(self):
        """Start the browser"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.firefox.launch(headless=self.headless)
        self.context = await self.browser.new_context(
            viewport={"width": self.viewport_width, "height": self.viewport_height}
        )
        self.page = await self.context.new_page()
        if self.downloads_folder:
            import os

            os.makedirs(self.downloads_folder, exist_ok=True)

            async def _handle_download(download):
                fname = download.suggested_filename
                target = os.path.join(self.downloads_folder or ".", fname)
                try:
                    await download.save_as(target)
                    self.last_download_path = target
                    self.logger.info(f"Download saved to {target}")
                except Exception as e:
                    self.logger.error(f"Download save failed: {e}")

            self.page.on("download", _handle_download)
        if self.show_overlay:
            await self.page.add_init_script(
                """() => {
                    if (document.getElementById('fara-debug-overlay')) return;
                    const el = document.createElement('div');
                    el.id = 'fara-debug-overlay';
                    el.style.position = 'fixed';
                    el.style.bottom = '8px';
                    el.style.right = '8px';
                    el.style.maxWidth = '42vw';
                    el.style.padding = '10px 12px';
                    el.style.borderRadius = '10px';
                    el.style.font = '12px/1.45 \"Fira Code\", Menlo, Consolas, monospace';
                    el.style.color = '#e9f5ff';
                    el.style.background = 'linear-gradient(145deg, rgba(12,17,28,0.92), rgba(20,32,52,0.9))';
                    el.style.border = '1px solid rgba(255,255,255,0.14)';
                    el.style.zIndex = '2147483647';
                    el.style.pointerEvents = 'none';
                    el.style.boxShadow = '0 8px 20px rgba(0,0,0,0.45)';
                    el.style.whiteSpace = 'pre-wrap';
                    el.style.backdropFilter = 'blur(6px)';
                    el.style.maxHeight = '42vh';
                    el.style.overflow = 'hidden';
                    el.style.display = 'flex';
                    el.style.flexDirection = 'column';
                    el.style.gap = '4px';
                    el.style.textAlign = 'left';
                    el.textContent = 'Fara debug overlay ready.';
                    document.body.appendChild(el);
                }"""
            )
            await self._inject_overlay()
        if self.show_click_markers:
            await self.page.add_init_script(
                """() => {
                    if (document.getElementById('fara-click-marker')) return;
                    const el = document.createElement('div');
                    el.id = 'fara-click-marker';
                    el.style.position = 'fixed';
                    el.style.width = '30px';
                    el.style.height = '30px';
                    el.style.borderRadius = '50%';
                    el.style.border = '2px solid #5bd1ff';
                    el.style.boxShadow = '0 0 12px rgba(91,209,255,0.65)';
                    el.style.background = 'rgba(91,209,255,0.15)';
                    el.style.zIndex = '2147483647';
                    el.style.pointerEvents = 'none';
                    el.style.transform = 'translate(-50%, -50%)';
                    el.style.display = 'none';
                    const label = document.createElement('div');
                    label.id = 'fara-click-marker-label';
                    label.style.position = 'absolute';
                    label.style.bottom = '-14px';
                    label.style.left = '50%';
                    label.style.transform = 'translateX(-50%)';
                    label.style.font = '11px/1.2 \"Fira Code\", Menlo, Consolas, monospace';
                    label.style.padding = '2px 6px';
                    label.style.borderRadius = '6px';
                    label.style.background = 'rgba(0,0,0,0.7)';
                    label.style.color = '#e9f5ff';
                    label.style.whiteSpace = 'nowrap';
                    label.style.boxShadow = '0 2px 6px rgba(0,0,0,0.35)';
                    label.textContent = 'click';
                    el.appendChild(label);
                    document.body.appendChild(el);
                }"""
            )
            await self._inject_click_marker()
        self.logger.info("Browser started")
    
    async def close(self):
        """Close the browser"""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        self.logger.info("Browser closed")
    
    async def goto(self, url: str):
        """Navigate to a URL"""
        await self.page.goto(url, wait_until="load", timeout=30000)
        await asyncio.sleep(0.5)
        if self.show_overlay and self._last_overlay_text:
            await self.restore_overlay_text()
    
    async def screenshot(self) -> bytes:
        """Take a screenshot"""
        overlay_was_visible = False
        marker_was_visible = False
        if self.show_overlay and self._overlay_created:
            try:
                overlay_was_visible = await self.page.evaluate(
                    """() => {
                        const el = document.getElementById('fara-debug-overlay');
                        if (!el) return false;
                        const wasVisible = el.style.display !== 'none';
                        el.style.display = 'none';
                        return wasVisible;
                    }"""
                )
            except Exception as e:
                self.logger.warning(f"Failed to hide overlay before screenshot: {e}")
        if self.show_click_markers and self._marker_created:
            try:
                marker_was_visible = await self.page.evaluate(
                    """() => {
                        const el = document.getElementById('fara-click-marker');
                        if (!el) return false;
                        const wasVisible = el.style.display !== 'none';
                        el.style.display = 'none';
                        return wasVisible;
                    }"""
                )
            except Exception as e:
                self.logger.warning(f"Failed to hide click marker before screenshot: {e}")
        shot = await self.page.screenshot()
        if self.show_overlay and self._overlay_created and overlay_was_visible:
            try:
                await self.page.evaluate(
                    """() => {
                        const el = document.getElementById('fara-debug-overlay');
                        if (el) el.style.display = 'block';
                    }"""
                )
            except Exception as e:
                self.logger.warning(f"Failed to restore overlay after screenshot: {e}")
        if self.show_click_markers and self._marker_created and marker_was_visible:
            try:
                await self.page.evaluate(
                    """() => {
                        const el = document.getElementById('fara-click-marker');
                        if (el) el.style.display = 'block';
                    }"""
                )
            except Exception as e:
                self.logger.warning(f"Failed to restore click marker after screenshot: {e}")
        return shot

    async def get_scroll_position(self) -> dict:
        """Return scroll position info for the current page."""
        try:
            return await self.page.evaluate(
                """() => {
                    const y = window.scrollY || 0;
                    const x = window.scrollX || 0;
                    const h = Math.max(
                        document.body.scrollHeight || 0,
                        document.documentElement.scrollHeight || 0
                    );
                    const w = Math.max(
                        document.body.scrollWidth || 0,
                        document.documentElement.scrollWidth || 0
                    );
                    const vh = window.innerHeight || 1;
                    const vw = window.innerWidth || 1;
                    return { x, y, scrollHeight: h, scrollWidth: w, viewportH: vh, viewportW: vw };
                }"""
            )
        except Exception:
            return {"x": 0, "y": 0, "scrollHeight": 0, "scrollWidth": 0, "viewportH": 0, "viewportW": 0}
    
    async def click(self, x: float, y: float):
        """Click at coordinates"""
        await self.page.mouse.click(x, y)
        await asyncio.sleep(0.3)
    
    async def hover(self, x: float, y: float):
        """Move cursor without clicking"""
        await self.page.mouse.move(x, y)
        await asyncio.sleep(0.2)
    
    async def type_text(self, text: str, press_enter: bool = False, delete_existing_text: bool = False):
        """Type text, optionally clearing existing input"""
        if delete_existing_text:
            await self.page.keyboard.press("Control+A")
            await self.page.keyboard.press("Backspace")
            await asyncio.sleep(0.15)
        await self.page.keyboard.type(text)
        if press_enter:
            await self.page.keyboard.press("Enter")
        await asyncio.sleep(0.3)
    
    async def press_key(self, key: str):
        """Press a keyboard key"""
        await self.page.keyboard.press(key)
        await asyncio.sleep(0.3)
    
    async def scroll(self, pixels: int):
        """Scroll the page (positive=up, negative=down)"""
        await self.page.mouse.wheel(0, -pixels)
        await asyncio.sleep(0.3)
    
    async def page_up(self):
        """Scroll up one page via keyboard"""
        await self.page.keyboard.press("PageUp")
        await asyncio.sleep(0.3)
    
    async def page_down(self):
        """Scroll down one page via keyboard"""
        await self.page.keyboard.press("PageDown")
        await asyncio.sleep(0.3)
    
    async def go_back(self):
        """Go back in history"""
        await self.page.go_back()
        await asyncio.sleep(0.5)
    
    def get_url(self) -> str:
        """Get current URL"""
        return self.page.url

    async def _inject_overlay(self):
        """Inject a debug overlay for headful debugging; hidden during screenshots."""
        try:
            created = await self.page.evaluate(
                """() => {
                    const existing = document.getElementById('fara-debug-overlay');
                    if (existing) return true;
                    const el = document.createElement('div');
                    el.id = 'fara-debug-overlay';
                    el.style.position = 'fixed';
                    el.style.bottom = '8px';
                    el.style.right = '8px';
                    el.style.maxWidth = '42vw';
                    el.style.padding = '10px 12px';
                    el.style.borderRadius = '10px';
                    el.style.font = '12px/1.45 \"Fira Code\", Menlo, Consolas, monospace';
                    el.style.color = '#e9f5ff';
                    el.style.background = 'linear-gradient(145deg, rgba(12,17,28,0.92), rgba(20,32,52,0.9))';
                    el.style.border = '1px solid rgba(255,255,255,0.14)';
                    el.style.zIndex = '2147483647';
                    el.style.pointerEvents = 'none';
                    el.style.boxShadow = '0 8px 20px rgba(0,0,0,0.45)';
                    el.style.whiteSpace = 'pre-wrap';
                    el.style.backdropFilter = 'blur(6px)';
                    el.style.maxHeight = '42vh';
                    el.style.overflow = 'hidden';
                    el.style.display = 'flex';
                    el.style.flexDirection = 'column';
                    el.style.gap = '4px';
                    el.style.textAlign = 'left';
                    el.textContent = 'Fara debug overlay ready.';
                    document.body.appendChild(el);
                    return true;
                }"""
            )
            self._overlay_created = bool(created)
        except Exception as e:
            self.logger.warning(f"Failed to inject overlay: {e}")

    async def update_overlay(self, text: str):
        """Update debug overlay text; no-op if overlay disabled."""
        if not self.show_overlay:
            return
        self._last_overlay_text = text
        if not self._overlay_created:
            await self._inject_overlay()
        try:
            updated = await self.page.evaluate(
                """(msg) => {
                    let el = document.getElementById('fara-debug-overlay');
                    if (!el) {
                        el = document.createElement('div');
                        el.id = 'fara-debug-overlay';
                        el.style.position = 'fixed';
                        el.style.bottom = '8px';
                        el.style.right = '8px';
                        el.style.maxWidth = '42vw';
                        el.style.padding = '10px 12px';
                        el.style.borderRadius = '10px';
                        el.style.font = '12px/1.45 \"Fira Code\", Menlo, Consolas, monospace';
                        el.style.color = '#e9f5ff';
                        el.style.background = 'linear-gradient(145deg, rgba(12,17,28,0.92), rgba(20,32,52,0.9))';
                        el.style.border = '1px solid rgba(255,255,255,0.14)';
                        el.style.zIndex = '2147483647';
                        el.style.pointerEvents = 'none';
                        el.style.boxShadow = '0 8px 20px rgba(0,0,0,0.45)';
                        el.style.whiteSpace = 'pre-wrap';
                        el.style.backdropFilter = 'blur(6px)';
                        el.style.maxHeight = '42vh';
                        el.style.overflow = 'hidden';
                        el.style.display = 'flex';
                        el.style.flexDirection = 'column';
                        el.style.gap = '4px';
                        el.style.textAlign = 'left';
                        document.body.appendChild(el);
                    }
                    el.textContent = msg;
                    return true;
                }""",
                text[:800],  # avoid unbounded content
            )
            self._overlay_created = self._overlay_created or bool(updated)
        except Exception as e:
            self.logger.warning(f"Failed to update overlay: {e}")

    async def restore_overlay_text(self):
        """Reapply the last overlay text after navigation."""
        if not self.show_overlay or not self._last_overlay_text:
            return
        await self.update_overlay(self._last_overlay_text)

    async def _inject_click_marker(self):
        """Ensure the click marker element exists."""
        try:
            created = await self.page.evaluate(
                """() => {
                    let el = document.getElementById('fara-click-marker');
                    if (el) return true;
                    el = document.createElement('div');
                    el.id = 'fara-click-marker';
                    el.style.position = 'fixed';
                    el.style.width = '30px';
                    el.style.height = '30px';
                    el.style.borderRadius = '50%';
                    el.style.border = '2px solid #5bd1ff';
                    el.style.boxShadow = '0 0 12px rgba(91,209,255,0.65)';
                    el.style.background = 'rgba(91,209,255,0.15)';
                    el.style.zIndex = '2147483647';
                    el.style.pointerEvents = 'none';
                    el.style.transform = 'translate(-50%, -50%)';
                    el.style.display = 'none';
                    const label = document.createElement('div');
                    label.id = 'fara-click-marker-label';
                    label.style.position = 'absolute';
                    label.style.bottom = '-14px';
                    label.style.left = '50%';
                    label.style.transform = 'translateX(-50%)';
                    label.style.font = '11px/1.2 "Fira Code", Menlo, Consolas, monospace';
                    label.style.padding = '2px 6px';
                    label.style.borderRadius = '6px';
                    label.style.background = 'rgba(0,0,0,0.7)';
                    label.style.color = '#e9f5ff';
                    label.style.whiteSpace = 'nowrap';
                    label.style.boxShadow = '0 2px 6px rgba(0,0,0,0.35)';
                    label.textContent = 'click';
                    el.appendChild(label);
                    document.body.appendChild(el);
                    return true;
                }"""
            )
            self._marker_created = bool(created)
        except Exception as e:
            self.logger.warning(f"Failed to inject click marker: {e}")

    async def show_click_marker(self, x: float, y: float, label: str = "click"):
        """Show a transient click marker at viewport coords; no-op if disabled."""
        if not self.show_click_markers:
            return
        if not self._marker_created:
            await self._inject_click_marker()
        try:
            await self.page.evaluate(
                """([vx, vy, lbl]) => {
                    const el = document.getElementById('fara-click-marker');
                    if (!el) return;
                    const labelEl = el.querySelector('#fara-click-marker-label');
                    if (labelEl) labelEl.textContent = lbl || 'click';
                    el.style.left = `${vx}px`;
                    el.style.top = `${vy}px`;
                    el.style.display = 'block';
                    setTimeout(() => {
                        const el2 = document.getElementById('fara-click-marker');
                        if (el2) el2.style.display = 'none';
                    }, 1000);
                }""",
                [x, y, label[:24]],
            )
        except Exception as e:
            self.logger.warning(f"Failed to show click marker: {e}")
