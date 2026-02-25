import os
import asyncio
import hashlib
import uuid
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from playwright.async_api import async_playwright
import httpx

# Shared Async HTTP Client for image recreation connection pooling
_image_recreator_client = httpx.AsyncClient(timeout=60.0)

class ImageRecreationService:
    def __init__(self, doc_obj=None):
        self.doc_obj = doc_obj
        self.llm = ChatOpenAI(
            model="cerebras/gpt-oss-120b",
            openai_api_base="https://bifrost.naravirtual.in/langchain",
            openai_api_key="dummy-key",
            default_headers={"Authorization": f"Basic {os.getenv('BIFROST_API_KEY')}"},
            temperature=0.1,
            http_async_client=_image_recreator_client
        )
        self.browser = None
        self.playwright = None

    def _count_images(self, data):
        count = 0
        if isinstance(data, list):
            for item in data:
                count += self._count_images(item)
        elif isinstance(data, dict):
            if data.get('image_strategy') == 'CANVAS':
                count += 1
            for v in data.values():
                count += self._count_images(v)
        return count

    async def process_structured_data(self, data):
        """Recursively find and process CANVAS image strategies with a shared browser."""
        total = self._count_images(data)
        if self.doc_obj:
            self.doc_obj.recreation_total_images = total
            self.doc_obj.recreation_completed_images = 0
            await asyncio.to_thread(self.doc_obj.save, update_fields=['recreation_total_images', 'recreation_completed_images'])

        if total == 0:
            return data

        async with async_playwright() as p:
            self.playwright = p
            self.browser = await p.chromium.launch(headless=True)
            
            # Use a semaphore to process X images in parallel to avoid overloading Gemini/System
            # Tuning: Reduced from 20 to 8 for better stability on medium-tier servers
            semaphore = asyncio.Semaphore(8)
            
            # We need to collect all tasks and run them
            tasks = []
            self._collect_tasks(data, tasks, semaphore)
            
            if tasks:
                print(f"🚀 Starting Parallel Image Recreation for {len(tasks)} images...")
                await asyncio.gather(*tasks)
            
            await self.browser.close()
            
        return data

    def _collect_tasks(self, data, tasks, semaphore):
        """Recursively find CANVAS blocks and add them to the task list."""
        if isinstance(data, list):
            for item in data:
                self._collect_tasks(item, tasks, semaphore)
        elif isinstance(data, dict):
            if data.get('image_strategy') == 'CANVAS' and data.get('image_details'):
                # We pass the dict reference so it can be updated in place
                tasks.append(self._recreate_and_update(data, semaphore))
            
            for v in data.values():
                if v is not None:
                    self._collect_tasks(v, tasks, semaphore)

    async def _recreate_and_update(self, image_block, semaphore):
        """Worker task that handles one image with a shared browser instance."""
        async with semaphore:
            result = await self.recreate_canvas(image_block.get('image_details', ''))
            if result:
                image_block['recreated_image_url'] = result.get('url')
                image_block['recreated_html_source'] = result.get('html')

    async def recreate_canvas(self, instructions: str):
        if not instructions or not self.browser:
            return None
            
        try:
            print(f"🎨 Recreating Canvas for: {instructions[:50]}...")
            
            # 1. Generate JS Code & Logic
            system_prompt = """You are a master of Data Visualization and HTML5 Canvas. 
Create a professional academic diagram based on the instructions.
- Target: Clean, high-resolution, vector-like quality.
- Responsiveness: The drawing should adapt to its container or define its own logical bounds.
- Quality: Use elegant colors (e.g., slate, indigo, emerald), anti-aliased lines, and clear typography.
- Output: Provide a COMPLETE self-contained HTML snippet.
- Structure: 
  <canvas id="canvas"></canvas>
  <script>
    const canvas = document.getElementById('canvas');
    const ctx = canvas.getContext('2d');
    // ... your drawing logic ...
    // IMPORTANT: Ensure the canvas has specific width/height set in JS if needed, 
    // or calculate logical bounds.
  </script>
Output ONLY the HTML/Script code. NO markdown backticks."""
            
            messages = [SystemMessage(content=system_prompt), HumanMessage(content=instructions)]
            res = await self.llm.ainvoke(messages)
            raw_html = res.content.strip().replace('```html', '').replace('```', '')
            
            # 2. Render with Dynamic Resolution
            page = await self.browser.new_page()
            
            # Inject the generated HTML
            full_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ margin: 0; padding: 20px; background: transparent; display: inline-block; }}
                    canvas {{ display: block; max-width: 100%; height: auto; }}
                </style>
            </head>
            <body>
                {raw_html}
            </body>
            </html>
            """
            
            await page.set_content(full_html)
            
            # Auto-sizing logic: Wait for canvas to be sized/rendered
            # We evaluate the bounding box of the canvas to get dynamic resolution
            await asyncio.sleep(1.0) # Wait for potential JS execution
            
            canvas_handle = await page.query_selector("canvas")
            if not canvas_handle:
                await page.close()
                return None
                
            # Take a high-DPI screenshot of just the canvas element
            # This handles dynamic resolution automatically
            buffer = await canvas_handle.screenshot(
                type="png",
                omit_background=True,
                animations="disabled"
            )
            await page.close()
            
            # 3. Save to Django Storage
            file_name = f"recreated/{uuid.uuid4()}.png"
            path = await asyncio.to_thread(default_storage.save, file_name, ContentFile(buffer))
            url = default_storage.url(path)

            # 4. Update Progress
            if self.doc_obj:
                from django.db.models import F
                from ..models import ParsedDocument
                await asyncio.to_thread(
                    ParsedDocument.objects.filter(id=self.doc_obj.id).update,
                    recreation_completed_images=F('recreation_completed_images') + 1
                )
            
            return {"url": url, "html": raw_html}

        except Exception as e:
            print(f"❌ Canvas Recreation Error: {e}")
            return None
