from django.utils.safestring import mark_safe

SEO_VALUABLE_CONTENT = {
    'rgpv-exam-form-last-date': {
        'sections': [
            {
                'title': 'How to Fill RGPV Exam Form',
                'content': mark_safe("""
                    <p>RGPV Exam forms are filled online through the official student portal. Follow these steps:</p>
                    <ul class="list-disc pl-5 mt-2 space-y-1">
                        <li>Login to <strong>rgpv.ac.in</strong> using your enrollment number.</li>
                        <li>Navigate to the 'Student Life' -> 'Exam Form' section.</li>
                        <li>Ensure your college has forwarded your form and entered sessional marks.</li>
                        <li>Pay the examination fee online via Net Banking, Credit/Debit Card or UPI.</li>
                    </ul>
                """)
            },
            {
                'title': 'Late Fee Structure',
                'content': mark_safe("""
                    <div class="overflow-x-auto mt-2">
                        <table class="w-full border-collapse border border-border text-sm">
                            <thead>
                                <tr class="bg-muted">
                                    <th class="border border-border p-2 text-left">Period</th>
                                    <th class="border border-border p-2 text-left">Fee Amount</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr>
                                    <td class="border border-border p-2">Standard Window</td>
                                    <td class="border border-border p-2">Normal Exam Fee (~₹1300-1850)</td>
                                </tr>
                                <tr>
                                    <td class="border border-border p-2">First Late Window</td>
                                    <td class="border border-border p-2">Normal Fee + ₹100</td>
                                </tr>
                                <tr>
                                    <td class="border border-border p-2">Extended Window</td>
                                    <td class="border border-border p-2">Normal Fee + ₹100/day late fee</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                """)
            }
        ],
        'faqs': [
            {'q': 'What is the standard RGPV exam fee?', 'a': 'For B.Tech, it usually ranges between ₹1300 to ₹1850 per semester.'},
            {'q': 'Can I fill the exam form after the last date?', 'a': 'Yes, but a late fee will apply. Initially ₹100, then ₹100 per day.'}
        ],
        'cta': 'Prepare your subjects now to avoid last-minute stress.'
    },
    'rgpv-grace-marks': {
        'sections': [
            {
                'title': 'General Grace Marks Rule',
                'content': mark_safe("""
                    <p>RGPV provides a maximum of <strong>5 grace marks</strong> in a single academic year. This can be used if:</p>
                    <ul class="list-disc pl-5 mt-2 space-y-1">
                        <li>You are falling short of passing marks in 1 or 2 subjects.</li>
                        <li>The total marks required to pass across all subjects does not exceed 5.</li>
                        <li>You have cleared all other subjects in the current semester.</li>
                    </ul>
                """)
            },
            {
                'title': 'Special Case: Division Grace',
                'content': mark_safe("""
                    <p>The Vice-Chancellor (VC) can award <strong>1 single grace mark</strong> if a student is missing out on a First Division or Distinction by exactly one mark, provided the student hasn't taken any other grace marks in that semester.</p>
                """)
            }
        ]
    },
    'rgpv-grading-system': {
        'sections': [
            {
                'title': 'RGPV SGPA to Percentage Formula',
                'content': mark_safe("""
                    <p>The official formula used by RGPV for converting CGPA/SGPA to percentage is:</p>
                    <div class="bg-muted p-4 rounded-lg my-4 text-lg font-mono text-center">
                        Percentage (%) = (CGPA - 0.5) × 10
                    </div>
                    <p>Example: If your CGPA is 8.5, your percentage would be (8.5 - 0.5) * 10 = 80%.</p>
                """)
            },
            {
                'title': 'Grade Point Scale',
                'content': mark_safe("""
                    <ul class="grid grid-cols-2 md:grid-cols-4 gap-2 mt-2">
                        <li class="p-2 border border-border rounded">A+: 10 (91-100)</li>
                        <li class="p-2 border border-border rounded">A: 9 (81-90)</li>
                        <li class="p-2 border border-border rounded">B+: 8 (71-80)</li>
                        <li class="p-2 border border-border rounded">B: 7 (61-70)</li>
                    </ul>
                """)
            }
        ]
    },
    'rgpv-pass-in-one-night-guide': {
        'sections': [
            {
                'title': 'The 3-Unit Strategy',
                'content': mark_safe("""
                    <p>Don't try to read everything. Focus on <strong>3 units perfectly</strong>. RGPV exams require you to attempt 5 out of 8 questions. Covering 3 units thoroughly gives you a solid chance to attempt 4-5 questions confidently.</p>
                """)
            },
            {
                'title': 'The Power of PYQs',
                'content': mark_safe("""
                    <p>Last 5 year Previous Year Questions (PYQs) are your best friend. Approximately 40-50% of the paper consists of repeated concepts or direct questions from previous years.</p>
                """)
            }
        ],
        'faqs': [
            {'q': 'Can I pass a subject if I only study 2 units?', 'a': 'It is risky. Studying 3 units thoroughly is the safest way to cover the required 5 questions.'},
            {'q': 'Is it true that RGPV repeats questions?', 'a': 'Yes, almost 40-50% of the paper is based on previous 5-year patterns.'}
        ],
        'cta': 'Browse our curated Important Questions for your subject.'
    },
    'rgpv-exam-tips': {
        'sections': [
            {
                'title': 'Presentation is Key',
                'content': mark_safe("""
                    <ul class="list-disc pl-5 space-y-2">
                        <li><strong>Use Diagrams:</strong> Even if not asked, draw flowcharts or block diagrams. Evaluators love visual clarity.</li>
                        <li><strong>Point-wise Answers:</strong> Avoid long paragraphs. Use bullets for readability.</li>
                        <li><strong>New Page Rule:</strong> Always start a new question (e.g., Q1 to Q2) on a fresh page.</li>
                        <li><strong>Highlights:</strong> Underline key terms or final answers in numericals.</li>
                    </ul>
                """)
            }
        ]
    },
    'rgpv-result': {
        'sections': [
            {
                'title': 'How to Check Your Result',
                'content': mark_safe("""
                    <p>Results are officially announced on <strong>rgpv.ac.in</strong>. Go to the 'Examination' -> 'Result' portal and enter your enrollment number and semester.</p>
                """)
            },
            {
                'title': 'Typical Result Window',
                'content': mark_safe("""
                    <p>RGPV usually declares results between <strong>45 to 60 days</strong> after the last theory examination of the session.</p>
                """)
            }
        ]
    },
    'rgpv-notes': {
        'sections': [
            {
                'title': 'Why Use CampusPrep RGPV Notes?',
                'content': mark_safe("""
                    <ul class="list-disc pl-5 space-y-2">
                        <li><strong>AI-Structured:</strong> No messy scans. Our AI parses handwritten and PDF notes into clean, searchable digital text.</li>
                        <li><strong>Unit-Wise:</strong> Perfectly aligned with the latest RGPV syllabus (Unit 1 to Unit 5).</li>
                        <li><strong>LaTeX Equations:</strong> Mathematical formulas and derivations are rendered sharply for easy reading on mobile.</li>
                        <li><strong>Ad-Free Experience:</strong> Focus strictly on your studies without distracting popups.</li>
                    </ul>
                """)
            }
        ],
        'cta': 'Unlock full access to unit-wise notes by logging in.'
    },
    'rgpv-most-asked-questions': {
        'sections': [
            {
                'title': 'Identifying Repeated Questions',
                'content': mark_safe("""
                    <p>In RGPV, certain questions carry high weightage and repeat every 2-3 years. Identifying these "Super Important" questions is half the battle won.</p>
                """)
            },
            {
                'title': 'How We Rank Questions',
                'content': mark_safe("""
                    <p>Our system analyzes the last 10 years of RGPV papers to highlight questions that have appeared more than 3 times. These are marked with a high "ROI" score in our subject dashboards.</p>
                """)
            }
        ]
    },
    'rgpv-result-date': {
        'sections': [
            {
                'title': 'RGPV Result Announcement Patterns',
                'content': mark_safe("""
                    <ul class="list-disc pl-5 mt-2 space-y-1">
                        <li><strong>Odd Semesters (1, 3, 5, 7):</strong> Exams in Dec/Jan -> Results usually in March/April.</li>
                        <li><strong>Even Semesters (2, 4, 6, 8):</strong> Exams in May/June -> Results usually in July/August.</li>
                        <li><strong>Final Years:</strong> RGPV prioritizes 8th semester results to facilitate placements and higher studies.</li>
                    </ul>
                """)
            }
        ]
    },
    'rgpv-exam-time-table': {
        'sections': [
            {
                'title': 'Accessing Latest Time Table',
                'content': mark_safe("""
                    <p>Always download the time table directly from the <strong>rgpv.ac.in</strong> portal. Avoid relying on WhatsApp forwards as RGPV often releases "Revised" versions just days before the exam.</p>
                """)
            }
        ]
    },
    'rgpv-revaluation-process': {
        'sections': [
            {
                'title': 'Revaluation vs Challenge Evaluation',
                'content': mark_safe("""
                    <p>If you are unhappy with your marks, RGPV offers two stages of review:</p>
                    <ul class="list-disc pl-5 mt-2 space-y-2">
                        <li><strong>Revaluation:</strong> A different examiner re-checks the paper. You must apply within 15 days of result declaration.</li>
                        <li><strong>Challenge Evaluation (Persuasion):</strong> If still unsatisfied, you can challenge the revaluation. Fee is typically ₹2000 per subject.</li>
                    </ul>
                """)
            },
            {
                'title': 'Important Rules',
                'content': mark_safe("""
                    <ul class="list-disc pl-5 space-y-1">
                        <li>No revaluation is allowed for Practical or Sessional exams.</li>
                        <li>Marks can decrease, increase, or stay the same.</li>
                        <li>If the marks increase by more than 10%, a portion of the challenge fee might be refunded.</li>
                    </ul>
                """)
            }
        ]
    },
    'rgpv-backlog-rules': {
        'sections': [
            {
                'title': 'ATKT & Promotion Policy (B.Tech)',
                'content': mark_safe("""
                    <p>RGPV follows a specific "Year-Back" policy for promotion:</p>
                    <ul class="list-disc pl-5 mt-2 space-y-2">
                        <li><strong>To reach 3rd Year (5th Sem):</strong> You must have cleared all subjects of the 1st Year.</li>
                        <li><strong>To reach 4th Year (7th Sem):</strong> You must have cleared all subjects of the 2nd Year.</li>
                        <li><strong>Maximum Backlogs:</strong> You cannot have more than 5-6 backlogs (Theory + Practical combined) to be promoted to the next year.</li>
                    </ul>
                """)
            }
        ]
    },
    'rgpv-passing-marks': {
        'sections': [
            {
                'title': 'Minimum Marks to Pass',
                'content': mark_safe("""
                    <div class="overflow-x-auto mt-2">
                        <table class="w-full border-collapse border border-border text-sm">
                            <thead>
                                <tr class="bg-muted">
                                    <th class="border border-border p-2 text-left">Exam Type</th>
                                    <th class="border border-border p-2 text-left">Max Marks</th>
                                    <th class="border border-border p-2 text-left">Min Passing</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr>
                                    <td class="border border-border p-2">Theory (End Sem)</td>
                                    <td class="border border-border p-2">70</td>
                                    <td class="border border-border p-2">22 (31%)</td>
                                </tr>
                                <tr>
                                    <td class="border border-border p-2">Practical/Sessional</td>
                                    <td class="border border-border p-2">30</td>
                                    <td class="border border-border p-2">15-18 (50-60%)</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                """)
            }
        ]
    },
    'rgpv-cgpa-calculation': {
        'sections': [
            {
                'title': 'Understanding the 10-Point Scale',
                'content': mark_safe("""
                    <p>RGPV uses a credit-based grading system. Your SGPA is calculated by multiplying subject credits with grade points earned.</p>
                    <ul class="grid grid-cols-2 gap-2 mt-4 font-mono text-xs">
                        <li class="p-2 border border-border rounded">A+ : 10 (Outstanding)</li>
                        <li class="p-2 border border-border rounded">A  : 9 (Excellent)</li>
                        <li class="p-2 border border-border rounded">B+ : 8 (Very Good)</li>
                        <li class="p-2 border border-border rounded">B  : 7 (Good)</li>
                        <li class="p-2 border border-border rounded">C+ : 6 (Average)</li>
                        <li class="p-2 border border-border rounded">C  : 5 (Below Average)</li>
                        <li class="p-2 border border-border rounded">D  : 4 (Pass)</li>
                        <li class="p-2 border border-border rounded">F  : 0 (Fail)</li>
                    </ul>
                """)
            }
        ]
    }
}
