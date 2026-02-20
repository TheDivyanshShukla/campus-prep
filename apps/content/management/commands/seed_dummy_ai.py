import json
from django.core.management.base import BaseCommand
from apps.academics.models import Branch, Semester, Subject
from apps.content.models import ParsedDocument

class Command(BaseCommand):
    help = 'Seeds dummy AI-parsed content for AI-DS Semester 1 Engineering Physics for UI testing.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING("Starting Dummy AI Content Seeding..."))

        # Find the specific subject
        branch = Branch.objects.filter(name__icontains='Artificial Intelligence').first()
        if not branch:
            self.stdout.write(self.style.ERROR("AI-DS Branch not found. Did you run seed_rgpv first?"))
            return

        semester = Semester.objects.filter(number=1).first()
        if not semester:
            self.stdout.write(self.style.ERROR("Semester 1 not found."))
            return

        subject = Subject.objects.filter(branch=branch, semester=semester, name__icontains='Physics').first()
        if not subject:
            self.stdout.write(self.style.ERROR(f"Physics subject not found for {branch.code} Sem {semester.number}."))
            return

        self.stdout.write(self.style.SUCCESS(f"Found target subject: {subject.name} ({subject.code})"))

        # Clear existing dummy data for this subject to prevent duplicates during re-runs
        ParsedDocument.objects.filter(subjects=subject).delete()

        # 1. Create a PYQ Document
        pyq_data = {
            "questions": [
                {
                    "unit": 1,
                    "marks": 7,
                    "has_or_choice": False,
                    "part": "Q.1 (a)",
                    "question_text": "State and prove Gauss's Divergence Theorem.",
                    "latex_answer": "Gauss's Divergence Theorem states that the outward flux of a vector field \\(\\vec{F}\\) across a closed surface \\(S\\) is equal to the volume integral of the divergence of \\(\\vec{F}\\) over the volume \\(V\\) enclosed by the surface.\n\nMathematically:\n\\[ \\iint_S \\vec{F} \\cdot d\\vec{S} = \\iiint_V (\\nabla \\cdot \\vec{F}) dV \\]\n\n**Proof Outline:**\n1. Consider an infinitesimal volume element \\(dV = dx\\,dy\\,dz\\).\n2. Calculate the net flux through the faces across the x, y, and z directions.\n3. Integrate over the entire volume \\(V\\) to show equivalence to the surface integral over \\(S\\)."
                },
                {
                    "unit": 2,
                    "marks": 7,
                    "has_or_choice": True,
                    "part": "Q.2 (b)",
                    "question_text": "Derive the Schrödinger time-independent wave equation for a free particle.",
                    "latex_answer": "The time-dependent Schrödinger equation is given by:\n\\[ i\\hbar \\frac{\\partial \\Psi}{\\partial t} = \\hat{H}\\Psi \\]\n\nFor a free particle, potential energy \\(V(x) = 0\\), so the Hamiltonian is purely kinetic:\n\\[ \\hat{H} = -\\frac{\\hbar^2}{2m} \\nabla^2 \\]\n\nAssuming a stationary state solution \\(\\Psi(\\vec{r}, t) = \\psi(\\vec{r})e^{-iEt/\\hbar}\\), we substitute this into the time-dependent equation:\n\n\\[ i\\hbar \\left( -\\frac{iE}{\\hbar} \\right) \\psi = -\\frac{\\hbar^2}{2m} \\nabla^2 \\psi \\]\n\n\\[ E\\psi = -\\frac{\\hbar^2}{2m} \\nabla^2 \\psi \\]\n\nRearranging gives the time-independent Schrödinger wave equation:\n\\[ \\nabla^2 \\psi + \\frac{2mE}{\\hbar^2} \\psi = 0 \\]"
                },
                {
                    "unit": 5,
                    "marks": 14,
                    "has_or_choice": False,
                    "part": "Q.8",
                    "question_text": "Explain the construction and working of a Ruby Laser with the help of a well-labeled energy level diagram.",
                    "latex_answer": "**Construction:**\n- **Active Medium**: A solid cylindrical ruby rod (Al₂O₃ doped with ~0.05% Cr³⁺ ions).\n- **Pumping Source**: A helical xenon flash lamp wrapped around the ruby rod.\n- **Optical Resonator**: The ends of the rod are polished flat and parallel. One end is fully silvered (100% reflective), and the other is partially silvered (~10% transmissive) to allow the laser beam to exit.\n\n**Working Principle (3-Level System):**\n1. **Pumping**: The xenon flash lamp emits intense white light. The Cr³⁺ ions absorb green (550 nm) and blue (400 nm) light, pumping electrons from the ground state \\(E_1\\) to excited bands \\(E_3\\).\n2. **Non-Radiative Decay**: Electrons rapidly drop from \\(E_3\\) to a metastable state \\(E_2\\) via non-radiative transitions, releasing heat to the crystal lattice.\n3. **Population Inversion**: Because \\(E_2\\) is metastable (longer lifetime ~3 ms), atoms accumulate there faster than they decay to \\(E_1\\), achieving population inversion between \\(E_2\\) and \\(E_1\\).\n4. **Stimulated Emission**: A spontaneous photon emitted by an \\(E_2 \\rightarrow E_1\\) transition (wavelength 694.3 nm) triggers stimulated emission from other Cr³⁺ ions in \\(E_2\\).\n5. **Amplification**: The photons bounce back and forth between the mirrors, building an intense cascade of coherent red light that eventually escapes through the partially silvered mirror."
                }
            ]
        }
        
        pyq_doc = ParsedDocument.objects.create(
            document_type='PYQ',
            title='2023 End Semester Examination',
            year=2023,
            structured_data=pyq_data,
            is_published=True
        )
        pyq_doc.subjects.add(subject)

        # 2. Create Chapter-wise Detailed Notes (1 for each Unit)
        for unit in range(1, 6):
            notes_data = {
                "title": f"Unit {unit} Detailed Notes",
                "content": f"These are deeply structured bullet points for Unit {unit}.\n\n- Advanced concept breakdown.\n- Mathematical derivations.\n- Real world applications."
            }
            notes_doc = ParsedDocument.objects.create(
                document_type='NOTES',
                title=f'Unit {unit}: Comprehensive Theory',
                year=None,
                structured_data=notes_data,
                is_published=True
            )
            notes_doc.subjects.add(subject)

        # 3. Create a Formula Sheet
        formula_data = {
            "formulas": [
                {"name": "De Broglie Wavelength", "latex": "\\lambda = \\frac{h}{p} = \\frac{h}{mv}"},
                {"name": "Energy of a photon", "latex": "E = h\\nu = \\frac{hc}{\\lambda}"},
                {"name": "Heisenberg Uncertainty", "latex": "\\Delta x \\cdot \\Delta p \ge \\frac{\\hbar}{2}"}
            ]
        }

        formula_doc = ParsedDocument.objects.create(
            document_type='FORMULA',
            title='Essential Physics Formulas',
            year=None,
            structured_data=formula_data,
            is_published=True
        )
        formula_doc.subjects.add(subject)

        # 4. Create a Syllabus
        syllabus_data = {
            "modules": [
                {"unit": 1, "topics": ["Wave-particle duality", "De Broglie hypothesis", "Phase and group velocity", "Heisenberg Uncertainty Principle", "Applications: Slit experiment"]},
                {"unit": 2, "topics": ["Wave mechanics", "Schrödinger time-dependent and independent equations", "Physical significance of wave function", "Particle in a 1D box", "Tunnel effect"]},
                {"unit": 3, "topics": ["Optics", "Interference in thin films", "Newton's rings", "Diffraction grating", "Resolving power"]},
                {"unit": 4, "topics": ["Lasers", "Spontaneous and stimulated emission", "Einstein's coefficients", "Population inversion", "Ruby and He-Ne Lasers"]},
                {"unit": 5, "topics": ["Fiber Optics", "Total internal reflection", "Acceptance angle and numerical aperture", "Types of optical fibers", "Attenuation"]}
            ]
        }
        syllabus_doc = ParsedDocument.objects.create(
            document_type='SYLLABUS',
            title='RGPV Prescribed Syllabus (Revised)',
            year=None,
            structured_data=syllabus_data,
            is_published=True
        )
        syllabus_doc.subjects.add(subject)

        # 5. Create Chapter-wise Short Notes (1 for each Unit)
        for unit in range(1, 6):
            short_notes_data = {
                "title": f"Unit {unit} Revision",
                "content": f"**Key Formulas & Definitions for Unit {unit}:**\n- Core concept 1\n- Core concept 2\n\n*Last minute exam refresher!*"
            }
            short_notes_doc = ParsedDocument.objects.create(
                document_type='SHORT_NOTES',
                title=f'Unit {unit}: Quick Revision',
                year=None,
                structured_data=short_notes_data,
                is_published=True
            )
            short_notes_doc.subjects.add(subject)

        # 6. Create Important Questions
        imp_q_data = {
            "questions": [
                {"text": "State and prove Heisenberg's Uncertainty Principle.", "frequency": "High"},
                {"text": "Derive Schrödinger's time-independent wave equation.", "frequency": "High"},
                {"text": "Explain the construction and working of a He-Ne Laser.", "frequency": "Medium"},
                {"text": "What is numerical aperture? Derive an expression for it.", "frequency": "High"}
            ]
        }
        ParsedDocument.objects.create(
            subject=subject,
            document_type='IMPORTANT_Q',
            title='Top Repeated Questions (2018-2023)',
            year=None,
            structured_data=imp_q_data,
            is_published=True
        )

        self.stdout.write(self.style.SUCCESS('Successfully seeded 6 high-quality AI documents for Engineering Physics (AI-DS, Sem 1).'))
