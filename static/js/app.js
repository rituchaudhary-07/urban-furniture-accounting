/* Urban Furniture Accounting System - Client Interactivity */

// Global Theme Toggle Functionality
window.toggleTheme = function() {
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('uf_theme', newTheme);
    updateThemeIcons(newTheme);
};

function updateThemeIcons(theme) {
    document.querySelectorAll('.theme-toggle-btn i').forEach(icon => {
        if (theme === 'light') {
            icon.className = 'fa-solid fa-sun';
        } else {
            icon.className = 'fa-solid fa-moon';
        }
    });
}

document.addEventListener('DOMContentLoaded', () => {
    // Set initial icon state
    const currentSavedTheme = localStorage.getItem('uf_theme') || 'dark';
    document.documentElement.setAttribute('data-theme', currentSavedTheme);
    updateThemeIcons(currentSavedTheme);

    // Modal Handlers
    window.openModal = function(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.add('show');
        }
    };

    window.closeModal = function(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('show');
        }
    };

    // Close modal on backdrop click
    document.querySelectorAll('.modal-backdrop').forEach(backdrop => {
        backdrop.addEventListener('click', (e) => {
            if (e.target === backdrop) {
                backdrop.classList.remove('show');
            }
        });
    });

    // Auto-calculate PO/SO line subtotals in forms
    const qtyInputs = document.querySelectorAll('.calc-qty, .calc-price');
    qtyInputs.forEach(input => {
        input.addEventListener('input', () => {
            const form = input.closest('form');
            if (form) {
                const qty = parseFloat(form.querySelector('.calc-qty')?.value || 0);
                const price = parseFloat(form.querySelector('.calc-price')?.value || 0);
                const totalElem = form.querySelector('.calc-total');
                if (totalElem) {
                    totalElem.textContent = `$${(qty * price).toFixed(2)}`;
                }
            }
        });
    });
});
