import json
import httpx
import asyncio
from django.core.management.base import BaseCommand
from apps.academics.models import Subject, SubjectAnalytics
from apps.content.models import ParsedDocument
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from typing import List
from langfuse.langchain import CallbackHandler

_ai_parser_client = httpx.AsyncClient(timeout=120.0)

# ---------------------------------------------------------
# Define Pydantic Schema for Structured Output
# ---------------------------------------------------------
class UnitROIMetric(BaseModel):
    unit_id: str = Field(description="The unit number as a string (e.g. '1', '2')")
    avg_marks: int = Field(description="Estimated average marks asked from this unit per year")
    efficiency: str = Field(description="'High', 'Medium', or 'Low'")
    name: str = Field(description="Unit Name")

class TopicHeatmapMetric(BaseModel):
    topic_name: str = Field(description="The exact topic name verbatim from the Syllabus")
    frequency: int = Field(description="Number of times asked")
    years: List[int] = Field(description="Array of years it was asked")
    unit: int = Field(description="Unit number it belongs to")

class ComplexityBreakdown(BaseModel):
    Theory: int = Field(description="Percentage 0-100 based on number of theory questions")
    Numerical: int = Field(description="Percentage 0-100 based on numericals")
    Design_Block_Diagrams: int = Field(alias="Design / Block Diagrams", description="Percentage 0-100 based on design/architecture")
    theory_examples: List[str] = Field(description="Up to 3 typical Theory questions strictly from this subject")
    numerical_examples: List[str] = Field(description="Up to 3 typical Numerical questions strictly from this subject")
    design_examples: List[str] = Field(description="Up to 3 typical Design/Block Diagram questions strictly from this subject")

class RepeatedQuestion(BaseModel):
    text: str = Field(description="Exact question text or simulated generic highly probable question")
    occurrences: int = Field(description="Number of times asked")
    years: List[int] = Field(description="Array of years asked")

class SubjectAnalyticsSchema(BaseModel):
    predictability_score: float = Field(description="Float 0-100 representing how repetitive the exams are based on past papers")
    unit_roi_data: List[UnitROIMetric] = Field(description="List of ROI metrics for each unit in the syllabus")
    syllabus_heatmap: List[TopicHeatmapMetric] = Field(description="List of frequency data for the most tested topics")
    complexity_breakdown: ComplexityBreakdown = Field(description="Complexity breakdown of the subject")
    top_repeated_questions: List[RepeatedQuestion] = Field(description="Top 5 repeated questions")

class Command(BaseCommand):
    help = 'Computes analytics data for specific subjects (bt201, bt102, bt205) using LLM'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Force re-computation even if analytics exist')

    def handle(self, *args, **options):
        asyncio.run(self.async_handle(*args, **options))

    async def async_handle(self, *args, **options):
        force = options.get('force')
        from asgiref.sync import sync_to_async
        
        # Group subjects by cleaned code
        @sync_to_async
        def get_all_subjects():
            return list(Subject.objects.filter(is_active=True))

        subjects = await get_all_subjects()
        
        from collections import defaultdict
        subjects_by_code = defaultdict(list)
        for subject in subjects:
            clean_code = subject.code.replace(' ', '').replace('-', '').upper()
            subjects_by_code[clean_code].append(subject)

        if not subjects_by_code:
            self.stdout.write(self.style.ERROR("No active subjects found in the database."))
            return

        import os
        
        # Build Dedicated Sync Client for High Concurrency Threads
        _analytics_client = httpx.Client(
            limits=httpx.Limits(max_connections=5000, max_keepalive_connections=1000)
        )
        
        # Build LLM
        llm = ChatOpenAI(
            model="openrouter/stepfun/step-3.5-flash:free",
            openai_api_base="https://bifrost.naravirtual.in/langchain",
            openai_api_key="dummy-key",
            default_headers={"Authorization": f"Basic {os.getenv('BIFROST_API_KEY')}"},
            http_client=_analytics_client,
            max_retries=0, # Handled manually in thread
            temperature=0.5,
        )
        structured_llm = llm.with_structured_output(SubjectAnalyticsSchema, method="json_mode")
        
        # Concurrency Control
        semaphore = asyncio.Semaphore(50000)

        async def process_subject_group(code, sub_list):
            async with semaphore:
                representative = sub_list[0]
                
                # 0. Check if analytics already exists
                @sync_to_async
                def check_exists():
                    return SubjectAnalytics.objects.filter(subject__in=sub_list).exists()
                
                if not force and await check_exists():
                    # self.stdout.write(f"Analytics already exist for {code}. Skipping...")
                    return

                # 1. Get parsed documents
                @sync_to_async
                def get_docs():
                    return list(ParsedDocument.objects.filter(
                        subjects=representative, 
                        document_type__in=['PYQ', 'UNSOLVED_PYQ'],
                        structured_data__isnull=False
                    ).values('year', 'title', 'structured_data'))
                
                docs_data = await get_docs()
                total_papers = len(docs_data)

                # Prepare syllabus
                @sync_to_async
                def get_units():
                    return list(representative.units.order_by('number').values('number', 'name', 'topics'))
                
                units_data = await get_units()
                syllabus_data = [{"unit_number": u['number'], "unit_name": u['name'], "topics": u['topics']} for u in units_data]

                # Retry logic for large/problematic subjects
                max_papers_options = [10, 5, 2, 0] # Gradually reduce papers to avoid 422/Context issues
                success = False
                
                def _sync_llm_call_with_retry(messages, paper_limit):
                    langfuse_handler = CallbackHandler()
                    for attempt in range(3):
                        try:
                            return structured_llm.invoke(
                                messages, 
                                config={
                                    "callbacks": [langfuse_handler],
                                    "metadata": {
                                        "langfuse_session_id": "global_analytics_threads",
                                        "langfuse_tags": ["bulk_generation", code, f"limit_{paper_limit}"]
                                    }
                                }
                            )
                        except Exception as e:
                            import time
                            time.sleep(1.5)
                            if attempt == 2:
                                raise e # Re-raise if all 3 attempts fail

                for paper_limit in max_papers_options:
                    try:
                        current_papers = docs_data[:paper_limit] if paper_limit > 0 else []
                        papers_payload = [{"year": d['year'], "title": d['title'], "data": d['structured_data']} for d in current_papers]

                        self.stdout.write(f"Processing {code} ({representative.name}) with {len(papers_payload)} papers...")

                        prompt_text = f"""
Analyze subject: {representative.name} ({representative.code}) for RGPV University.
SYLLABUS DATA: {json.dumps(syllabus_data, indent=2)}
PAST PAPERS ANALYZED: {len(papers_payload)}
PAST PAPERS DATA: {json.dumps(papers_payload)}

If past papers are few or empty, use your knowledge of Indian Engineering curriculum to simulate plausible trends based on labels/topics.
CRITICAL:
- Total complexity percentages must sum to 100.
- Use LaTeX ($...$ and $$...$$) for ALL mathematical formulas/variables.
- Provide subject-specific examples for Theory, Numerical, and Design.
"""
                        messages = [
                            SystemMessage(content="You are a senior academic data analyst API. Return valid JSON only."),
                            HumanMessage(content=prompt_text)
                        ]
                        
                        import concurrent.futures
                        if not hasattr(self, '_executor'):
                            self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1000)
                            
                        # Execute the synchronous LLM call safely in a separate explicit thread pool
                        loop = asyncio.get_running_loop()
                        parsedResult = await loop.run_in_executor(self._executor, _sync_llm_call_with_retry, messages, paper_limit)

                        # Transform and Save
                        @sync_to_async
                        def save_results(result):
                            unit_roi_data = {item.unit_id: {
                                "avg_marks": item.avg_marks, "efficiency": item.efficiency, "name": item.name
                            } for item in result.unit_roi_data}
                            
                            syllabus_heatmap = {item.topic_name: {
                                "frequency": item.frequency, "years": item.years, "unit": item.unit
                            } for item in result.syllabus_heatmap}
                            
                            complexity_breakdown = {
                                "Theory": result.complexity_breakdown.Theory,
                                "Numerical": result.complexity_breakdown.Numerical,
                                "Design / Block Diagrams": getattr(result.complexity_breakdown, "Design / Block Diagrams", result.complexity_breakdown.Design_Block_Diagrams),
                                "theory_examples": result.complexity_breakdown.theory_examples,
                                "numerical_examples": result.complexity_breakdown.numerical_examples,
                                "design_examples": result.complexity_breakdown.design_examples,
                            }
                            
                            top_repeated_questions = [q.dict() for q in result.top_repeated_questions]

                            for s in sub_list:
                                SubjectAnalytics.objects.update_or_create(
                                    subject=s,
                                    defaults={
                                        'predictability_score': float(result.predictability_score),
                                        'total_papers_analyzed': total_papers,
                                        'unit_roi_data': unit_roi_data,
                                        'syllabus_heatmap': syllabus_heatmap,
                                        'complexity_breakdown': complexity_breakdown,
                                        'top_repeated_questions': top_repeated_questions
                                    }
                                )

                        await save_results(parsedResult)
                        self.stdout.write(self.style.SUCCESS(f"Finished {code}"))
                        success = True
                        break

                    except Exception as e:
                        error_msg = str(e)
                        if "422" in error_msg or "context_length_exceeded" in error_msg:
                            self.stdout.write(self.style.WARNING(f"Retrying {code} with fewer papers due to payload size (Attempt {max_papers_options.index(paper_limit) + 1})..."))
                            continue
                        else:
                            self.stdout.write(self.style.ERROR(f"Error {code}: {error_msg[:150]}"))
                            break # Non-payload error, stop retrying this group

                if not success:
                    self.stdout.write(self.style.ERROR(f"Gave up on {code} after all retry attempts."))


        # Create tasks for all groups
        tasks = [process_subject_group(code, sub_list) for code, sub_list in subjects_by_code.items()]
        self.stdout.write(f"Launching {len(tasks)} concurrent tasks...")
        await asyncio.gather(*tasks)
        self.stdout.write(self.style.SUCCESS("All subjects processed."))


