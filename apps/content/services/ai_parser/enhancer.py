import os
import json
import asyncio
from typing import List, Optional, Union
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from .schemas import ParsedPYQPaper, ParsedUnsolvedPYQPaper
import httpx
import concurrent.futures



class PYQEnhancer:
    _executor = concurrent.futures.ThreadPoolExecutor(max_workers=500)
    
    def __init__(self):
        # We will use a dedicated synchronous client for this task
        _enhancer_client = httpx.Client(
            limits=httpx.Limits(max_connections=500, max_keepalive_connections=100)
        )
        self.llm = ChatOpenAI(
            model="openrouter/stepfun/step-3.5-flash:free",
            openai_api_base="https://bifrost.naravirtual.in/langchain",
            openai_api_key="dummy-key",
            default_headers={"Authorization": f"Basic {os.getenv('BIFROST_API_KEY')}"},
            http_client=_enhancer_client,
            max_retries=0, # We will handle retries manually
            temperature=0.5,
        )

    def _build_system_prompt(self, context: dict) -> str:
        return f"""You are an elite Academic Data Architect specializing in RGPV University engineering curriculum.
Your mission is to RE-LABEL and ENHANCE existing past paper questions using the provided official SYLLABUS as the absolute authority.

CONTEXT:
Subject: {context.get('subject_code')} - {context.get('subject_name')}

SYLLABUS REFERENCE:
{context.get('syllabus_json')}

RULES FOR ENHANCEMENT:
1. SYLLABUS IS THE GOSPEL: Match the question text to the most relevant module/unit in the syllabus.
2. RE-LABEL UNIT: Even if the input has a 'unit' number, you must overwrite it if the syllabus indicates it belongs elsewhere.
3. TOPIC NAME: Assign a specific topic or sub-topic from the syllabus (e.g., 'Newton's Rings', 'Schrödinger Equation').
4. COMPLEXITY: Rate as 'Easy', 'Medium', or 'Hard' based on standard engineering exam patterns.
5. BLOOMS TAXONOMY: Determine the cognitive level (Remember, Understand, Apply, Analyze, Evaluate, Create).
6. PRESERVE QUALITY: Do not change the original question text or marks. Only enhance the metadata.
"""

    async def enhance_questions(self, questions: List[dict], syllabus_data: dict, subject_context: dict, is_solved: bool = False) -> dict:        
        context = {
            **subject_context,
            'syllabus_json': json.dumps(syllabus_data, indent=2)
        }
        
        system_prompt = self._build_system_prompt(context)
        chunk_size = 10
        
        # 1. Use pure tool calling (structured output) instead of raw parsing
        schema = ParsedPYQPaper if is_solved else ParsedUnsolvedPYQPaper
        structured_llm = self.llm.with_structured_output(schema, method="json_mode")
        
        def _sync_enhance_batch_with_retry(chunk, batch_idx):
            from langfuse.langchain import CallbackHandler
            human_content = f"Here are {len(chunk)} questions to enhance:\n{json.dumps(chunk, indent=2)}"
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_content)
            ]
            
            langfuse_handler = CallbackHandler()
            
            # 2. Add retry logic up to 3 times
            for attempt in range(3):
                try:
                    result = structured_llm.invoke(
                        messages,
                        config={
                            "callbacks": [langfuse_handler],
                            "metadata": {
                                "langfuse_session_id": "global_pyq_enhancement_threads",
                                "langfuse_tags": ["enhancement", context.get('subject_code')]
                            }
                        }
                    )
                    
                    res_dict = result.model_dump() if hasattr(result, 'model_dump') else result
                    # Safely extract questions array
                    if 'questions' in res_dict:
                        return res_dict['questions']
                    elif 'enhanced_questions' in res_dict:
                        return res_dict['enhanced_questions']
                    elif isinstance(res_dict, list):
                        return res_dict
                    return []
                    
                except Exception as e:
                    import time
                    time.sleep(1.5) # small backoff
                    if attempt == 2:
                        print(f"  [Attempt {attempt + 1}/3] Failed for batch {batch_idx+1}: {e}")
                        
            print(f"  Batch {batch_idx+1} completely failed after 3 attempts.")
            return []

        # 3. Use an explicit ThreadPoolExecutor to bypass Python's default OS core limit
        loop = asyncio.get_running_loop()
        tasks = []
        for i in range(0, len(questions), chunk_size):
            chunk = questions[i:i+chunk_size]
            batch_idx = i // chunk_size
            tasks.append(loop.run_in_executor(self._executor, _sync_enhance_batch_with_retry, chunk, batch_idx))
            
        print(f"  Launched {len(tasks)} async threads for {len(questions)} questions.")
        
        results = await asyncio.gather(*tasks)
        
        enhanced_questions = []
        for batch_res in results:
            enhanced_questions.extend(batch_res)
                
        return {'questions': enhanced_questions}
