from playwright.sync_api import sync_playwright, expect
import time

def verify_app():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            # Navigate to app
            page.goto("http://localhost:5173")

            time.sleep(2)

            # Take debug screenshot
            page.screenshot(path="verification/debug_page.png")

            # Check title
            expect(page.get_by_text("Fara Agent")).to_be_visible()
            expect(page.get_by_text("Live View")).to_be_visible()

            # Take screenshot of initial state
            page.screenshot(path="verification/initial_ui.png")

            # Type a task
            input_box = page.get_by_placeholder("Enter a task")
            input_box.fill("Go to google.com")

            # Take screenshot of input
            page.screenshot(path="verification/input_ui.png")

            # Click Run
            page.get_by_role("button", name="Run").click()

            time.sleep(2)

            # Take screenshot of running state (or error state)
            page.screenshot(path="verification/running_ui.png")

        except Exception as e:
            print(f"Error: {e}")
            page.screenshot(path="verification/error_page.png")
        finally:
            browser.close()

if __name__ == "__main__":
    verify_app()
