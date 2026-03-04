/**
 * Base UI interactions: theme toggle, mobile menu, user dropdown, custom select dropdowns.
 */
(function () {
    'use strict';

    // ── Theme Toggle ─────────────────────────────────────────────────────────
    const toggleTheme = () => {
        if (document.documentElement.classList.contains('dark')) {
            document.documentElement.classList.remove('dark');
            localStorage.theme = 'light';
            document.cookie = 'theme=light; path=/; max-age=31536000';
        } else {
            document.documentElement.classList.add('dark');
            localStorage.theme = 'dark';
            document.cookie = 'theme=dark; path=/; max-age=31536000';
        }
    };

    const themeToggle = document.getElementById('themeToggle');
    if (themeToggle) themeToggle.addEventListener('click', toggleTheme);

    const mobileThemeToggle = document.getElementById('mobileThemeToggle');
    if (mobileThemeToggle) mobileThemeToggle.addEventListener('click', toggleTheme);

    // ── Mobile Menu ──────────────────────────────────────────────────────────
    const mobileMenuBtn = document.getElementById('mobileMenuBtn');
    const mobileMenu = document.getElementById('mobileMenu');
    const mobileMenuBackdrop = document.getElementById('mobileMenuBackdrop');
    const mobileMenuClose = document.getElementById('mobileMenuClose');

    function openMobileMenu() {
        mobileMenu.classList.remove('hidden');
        mobileMenuBackdrop.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
    }

    function closeMobileMenu() {
        mobileMenu.classList.add('hidden');
        mobileMenuBackdrop.classList.add('hidden');
        document.body.style.overflow = '';
    }

    if (mobileMenuBtn) mobileMenuBtn.addEventListener('click', openMobileMenu);
    if (mobileMenuClose) mobileMenuClose.addEventListener('click', closeMobileMenu);
    if (mobileMenuBackdrop) mobileMenuBackdrop.addEventListener('click', closeMobileMenu);
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeMobileMenu(); });

    // ── User Account Dropdown ────────────────────────────────────────────────
    const userDropdownBtn = document.getElementById('userDropdownBtn');
    const userDropdownMenu = document.getElementById('userDropdownMenu');
    const dropdownChevron = document.getElementById('dropdownChevron');

    if (userDropdownBtn && userDropdownMenu) {
        userDropdownBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const isHidden = userDropdownMenu.classList.contains('hidden');
            userDropdownMenu.classList.toggle('hidden', !isHidden);
            if (dropdownChevron) dropdownChevron.style.transform = isHidden ? 'rotate(180deg)' : '';
        });

        document.addEventListener('click', (e) => {
            if (!userDropdownBtn.contains(e.target) && !userDropdownMenu.contains(e.target)) {
                userDropdownMenu.classList.add('hidden');
                if (dropdownChevron) dropdownChevron.style.transform = '';
            }
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                userDropdownMenu.classList.add('hidden');
                if (dropdownChevron) dropdownChevron.style.transform = '';
            }
        });
    }

    // ── Custom Select Dropdowns ──────────────────────────────────────────────
    function initCustomDropdowns() {
        const selects = document.querySelectorAll('select:not(.no-custom)');

        selects.forEach(select => {
            if (select.parentElement.classList.contains('custom-select-container')) return;

            const container = document.createElement('div');
            container.className = 'custom-select-container';

            const trigger = document.createElement('button');
            trigger.type = 'button';
            trigger.className = 'custom-select-trigger';

            const selectedOption = select.options[select.selectedIndex];
            const triggerText = document.createElement('span');
            triggerText.className = 'flex-1 truncate';
            triggerText.textContent = selectedOption ? selectedOption.textContent : 'Select...';

            const icon = document.createElement('svg');
            icon.innerHTML = '<path d="M6 9l6 6 6-6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>';
            icon.className = 'w-4 h-4 ml-2 transition-transform duration-200';
            icon.setAttribute('fill', 'none');
            icon.setAttribute('viewBox', '0 0 24 24');

            trigger.appendChild(triggerText);
            trigger.appendChild(icon);

            const menu = document.createElement('div');
            menu.className = 'custom-select-menu';

            Array.from(select.options).forEach((option, index) => {
                const item = document.createElement('div');
                item.className = 'custom-select-option';
                if (index === select.selectedIndex) item.classList.add('selected');
                item.textContent = option.textContent;

                item.addEventListener('click', () => {
                    select.selectedIndex = index;
                    triggerText.textContent = option.textContent;

                    menu.querySelectorAll('.custom-select-option').forEach(opt => opt.classList.remove('selected'));
                    item.classList.add('selected');

                    menu.classList.remove('show');
                    icon.classList.remove('rotate-180');

                    select.dispatchEvent(new Event('change'));
                });

                menu.appendChild(item);
            });

            trigger.addEventListener('click', (e) => {
                e.stopPropagation();
                const isShowing = menu.classList.contains('show');

                document.querySelectorAll('.custom-select-menu.show').forEach(m => {
                    m.classList.remove('show');
                    m.previousElementSibling.querySelector('svg').classList.remove('rotate-180');
                });

                if (!isShowing) {
                    menu.classList.add('show');
                    icon.classList.add('rotate-180');
                }
            });

            select.style.display = 'none';

            container.appendChild(trigger);
            container.appendChild(menu);
            select.parentNode.insertBefore(container, select);
            container.appendChild(select);
        });
    }

    document.addEventListener('DOMContentLoaded', () => {
        initCustomDropdowns();
    });

    document.addEventListener('click', (e) => {
        if (!e.target.closest('.custom-select-container')) {
            document.querySelectorAll('.custom-select-menu.show').forEach(m => {
                m.classList.remove('show');
                m.previousElementSibling.querySelector('svg').classList.remove('rotate-180');
            });
        }
    });
})();
