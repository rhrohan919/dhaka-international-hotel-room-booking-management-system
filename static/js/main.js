document.addEventListener('DOMContentLoaded', function () {
    const messageContainer = document.querySelector('.message-container');
    if (messageContainer) {
        const alerts = messageContainer.querySelectorAll('.alert');
        alerts.forEach((alert) => {
            setTimeout(() => {
                alert.style.opacity = '0';
                alert.style.transform = 'translateY(-8px)';
                setTimeout(() => alert.remove(), 250);
            }, 3500);
        });
    }

    const faqItems = document.querySelectorAll('.faq-item');
    faqItems.forEach((item) => {
        const button = item.querySelector('.faq-question');
        if (!button) return;

        button.addEventListener('click', () => {
            const isActive = item.classList.contains('active');
            faqItems.forEach((faq) => {
                faq.classList.remove('active');
            });

            if (!isActive) {
                item.classList.add('active');
            }
        });
    });

    const yearNode = document.getElementById('current-year');
    if (yearNode) {
        yearNode.textContent = new Date().getFullYear();
    }
});
