import os
import asyncio
import json
import django
import sys
sys.path.append(os.getcwd())
# Initialize Django for standalone script usage
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.content.services.image_recreator import ImageRecreationService

async def test_recreation():
    # Mock data representing the structured output from AI
    mock_data = {
        "sections": [
            {
                "section_title": "Fluid Dynamics: Venturi Meter",
                "content_blocks": [
                    {
                        "type": "text",
                        "content": "A venturi meter is used for measuring the rate of a flow of a fluid flowing through a pipe."
                    },
                    {
                        "type": "image",
                        "image_strategy": "CANVAS",
                        "image_details": "Draw a high-quality horizontal venturi meter diagram. Show a pipe with a converging part, a throat, and a diverging part. Add dimension lines for D1 and D2. Use professional blue and gray tones."
                    }
                ]
            },
            {
                "section_title": "Bernoulli's Equation",
                "content_blocks": [
                    {
                        "type": "text",
                        "content": "For a fluid element, the pressure force plus gravity equals constant."
                    },
                    {
                        "type": "image",
                        "image_strategy": "CANVAS",
                        "image_details": "Draw a simple derivation diagram of a fluid element in a pipe inclined at an angle theta. Show pressure P1, P2 and weight W. Use arrows to show force directions."
                    }
                ]
            }
        ]
    }

    print("🚀 Initializing ImageRecreationService...")
    # Passing None for doc_obj as we don't need database updates for this test
    service = ImageRecreationService(doc_obj=None)
    
    print("🎨 Processing Mock Data (Recreating 2 Diagrams in Parallel)...")
    try:
        processed_data = await service.process_structured_data(mock_data)
        
        # Verify results
        print("\n✅ Processing Complete!")
        print("------------------------------------------")
        
        sections = processed_data.get('sections', [])
        for i, section in enumerate(sections):
            for block in section.get('content_blocks', []):
                if block.get('type') == 'image':
                    url = block.get('recreated_image_url')
                    print(f"Block {i+1} [{block['image_strategy']}]:")
                    print(f"  Details: {block['image_details'][:60]}...")
                    print(f"  Rendered URL: {url}")
        
        print("------------------------------------------")
        
    except Exception as e:
        print(f"❌ Test Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_recreation())
