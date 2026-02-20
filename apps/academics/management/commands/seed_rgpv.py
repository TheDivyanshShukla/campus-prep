import json
from django.core.management.base import BaseCommand
from apps.academics.models import Branch, Semester, Subject, Unit

class Command(BaseCommand):
    help = 'Seeds the database with all RGPV standard Branches, Semesters, and Subjects based on the new curriculum.'

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting Comprehensive RGPV Seeding Process...")

        # 1. Seed Semesters (1 to 8)
        semesters = {}
        for i in range(1, 9):
            sem, created = Semester.objects.get_or_create(number=i)
            semesters[i] = sem

        # 2. Seed Branches
        branches_data = [
            ("Computer Science & Engineering", "CSE"),
            ("Information Technology", "IT"),
            ("Electronics & Communication Engineering", "ECE"),
            ("Mechanical Engineering", "ME"),
            ("Civil Engineering", "CE"),
            ("Electrical & Electronics Engineering", "EX"),
            ("Artificial Intelligence & Data Science", "AD"),
            ("Automobile Engineering", "AU"),
        ]
        
        branches = {}
        for name, code in branches_data:
            branch, created = Branch.objects.get_or_create(code=code, defaults={'name': name})
            branches[code] = branch

        # 3. First Year Common Subjects
        first_year_physics = [
            ("BT-201", "Engineering Physics"),
            ("BT-102", "Mathematics-I"),
            ("BT-203", "Basic Mechanical Engineering"),
            ("BT-204", "Basic Civil Engineering & Mechanics"),
            ("BT-205", "Basic Computer Engineering"),
            ("BT-206", "Language Lab & Seminars"),
        ]
        
        first_year_chemistry = [
            ("BT-101", "Engineering Chemistry"),
            ("BT-202", "Mathematics-II"),
            ("BT-103", "English for Communication"),
            ("BT-104", "Basic Electrical & Electronics Engineering"),
            ("BT-105", "Engineering Graphics"),
            ("BT-106", "Manufacturing Practices"),
        ]

        # Group A Branches: CSE, IT, EX (Chem Sem 1, Physics Sem 2)
        group_a = ['CSE', 'IT', 'EX']
        # Group B Branches: AD, ECE, ME, CE, AU (Physics Sem 1, Chem Sem 2)
        group_b = ['AD', 'ECE', 'ME', 'CE', 'AU']

        all_curriculum = {
            'CSE': {
                3: [("CS-302", "Discrete Structure"), ("CS-303", "Data Structure"), ("CS-304", "Digital Systems"), ("CS-305", "Object Oriented Programming & Methodology"), ("ES-301", "Energy & Environmental Engineering"), ("CS-306", "Computer Workshop")],
                4: [("CS-402", "Analysis Design of Algorithm"), ("CS-403", "Software Engineering"), ("CS-404", "Computer Organization & Architecture"), ("CS-405", "Operating Systems"), ("BT-401", "Mathematics-III"), ("BT-408", "Cyber Security")],
                5: [("CS-501", "Theory of Computation"), ("CS-502", "Database Management Systems")],
                6: [("CS-601", "Compiler Design"), ("CS-602", "Computer Networks")],
                7: [("CS-701", "Software Architectures")],
                8: [("CS-801", "Major Project-II")]
            },
            'IT': {
                3: [("IT-302", "Discrete Structure"), ("IT-303", "Data Structures"), ("IT-304", "Object Oriented Programming & Methodology"), ("IT-305", "Digital Systems")],
                4: [("IT-402", "Computer Networks"), ("IT-403", "Analysis Design of Algorithm"), ("IT-404", "Computer Organization & Architecture"), ("IT-405", "Operating Systems")],
                5: [("IT-501", "Theory of Computation")],
                6: [("IT-601", "Software Engineering")],
                7: [("IT-701", "Cloud Computing")],
                8: [("IT-801", "Information Security")]
            },
            'ECE': {
                3: [("EC-302", "Electronic Devices"), ("EC-303", "Digital System Design"), ("EC-304", "Network Analysis"), ("EC-305", "Signals & Systems")],
                4: [("EC-402", "Analog Communication"), ("EC-403", "Control Systems"), ("EC-404", "Linear Integrated Circuits"), ("EC-405", "Analog Circuits")],
                5: [("EC-502", "Digital Communication")],
                6: [("EC-602", "Digital Signal Processing")],
                7: [("EC-701", "Microwave Engineering")],
                8: [("EC-801", "VLSI Design")]
            },
            'ME': {
                3: [("ME-302", "Thermodynamics"), ("ME-303", "Materials Technology"), ("ME-304", "Strength of Materials"), ("ME-305", "Manufacturing Process")],
                4: [("ME-402", "Fluid Mechanics"), ("ME-403", "Machine Design-I"), ("ME-404", "Kinematics of Machines"), ("ME-405", "Thermal Engineering")],
                5: [("ME-501", "Internal Combustion Engines")],
                6: [("ME-603", "Heat & Mass Transfer")],
                7: [("ME-702", "Automobile Engineering")],
                8: [("ME-801", "Refrigeration & Air Conditioning")]
            },
            'CE': {
                3: [("CE-302", "Surveying"), ("CE-303", "Building Planning & Architecture"), ("CE-304", "Strength of Materials"), ("CE-305", "Engineering Geology")],
                4: [("CE-402", "Fluid Mechanics"), ("CE-403", "Structural Analysis-I"), ("CE-404", "Water Supply Engineering"), ("CE-405", "Concrete Technology")],
                5: [("CE-502", "Design of Concrete Structures")],
                6: [("CE-604", "Geotechnical Engineering")],
                7: [("CE-701", "Advanced Structural Design")],
                8: [("CE-801", "Geo-informatics")]
            },
            'EX': {
                3: [("EX-302", "Electrical Measurements"), ("EX-303", "Network Analysis"), ("EX-304", "Electronic Devices"), ("EX-305", "Signals & Systems")],
                4: [("EX-402", "Digital Electronics"), ("EX-403", "Power System-I"), ("EX-404", "Electrical Machines-I"), ("EX-405", "Control Systems")],
                5: [("EX-502", "Power Electronics")],
                6: [("EX-601", "Power System-II")],
                7: [("EX-701", "High Voltage Engineering")],
                8: [("EX-801", "Power Quality")]
            },
            'AD': {
                3: [("AD-302", "Statistical Methods"), ("AD-303", "Data Structures"), ("AD-304", "Introduction to AI"), ("AD-305", "Digital Systems")],
                4: [("AD-402", "Database Management Systems"), ("AD-403", "Analysis Design of Algorithm"), ("AD-404", "Introduction to ML"), ("AD-405", "Operating Systems")],
                5: [("AD-501", "Theory of Computation")],
                6: [("CD-601", "Advanced AI")],
                7: [("CD-701", "Data Science Statistics")],
                8: [("CD-801", "Deep Learning")]
            },
            'AU': {
                3: [("AU-302", "Thermodynamics"), ("AU-303", "Theory of Machines"), ("AU-304", "Strength of Materials"), ("AU-305", "Manufacturing Process")],
                4: [("AU-402", "Fluid Mechanics"), ("AU-403", "Automobile Chassis"), ("AU-404", "Internal Combustion Engines"), ("AU-405", "Mechanical Measurements")],
                5: [("AU-504", "Vehicle Dynamics")],
                6: [("AU-604", "Electric & Hybrid Vehicles")],
                7: [("AU-701", "Vehicle Diagnostics")],
                8: [("AU-801", "Automotive Transport Management")]
            }
        }

        # Apply First Year Logic to all curriculums
        for b_code in group_a:
            all_curriculum[b_code][1] = first_year_chemistry
            all_curriculum[b_code][2] = first_year_physics
            
        for b_code in group_b:
            all_curriculum[b_code][1] = first_year_physics
            all_curriculum[b_code][2] = first_year_chemistry

        subject_count = 0
        unit_count = 0

        # Execute Seeding
        for branch_code, sems in all_curriculum.items():
            branch_instance = branches[branch_code]
            for sem_num, subjects in sems.items():
                sem_instance = semesters[sem_num]
                
                for code, name in subjects:
                    subject, created = Subject.objects.get_or_create(
                        branch=branch_instance,
                        semester=sem_instance,
                        code=code,
                        defaults={'name': name}
                    )
                    if created:
                        subject_count += 1
                    
                    # Create exactly 5 Units per subject
                    for unit_idx in range(1, 6):
                        unit, u_created = Unit.objects.get_or_create(
                            subject=subject,
                            number=unit_idx,
                            defaults={'name': f"Unit {unit_idx} - Core Syllabus"}
                        )
                        if u_created:
                            unit_count += 1

        self.stdout.write(self.style.SUCCESS(f"Successfully seeded {subject_count} Subjects and {unit_count} Units across 8 Branches!"))
