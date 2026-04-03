document.addEventListener('DOMContentLoaded', () => {
    // 1. Magnetic Buttons Implementation
    const magnets = document.querySelectorAll('.btn-magnetic');
    
    magnets.forEach((magnet) => {
        magnet.addEventListener('mousemove', (e) => {
            const position = magnet.getBoundingClientRect();
            const x = e.pageX - position.left - window.scrollX;
            const y = e.pageY - position.top - window.scrollY;
            
            const centerX = position.width / 2;
            const centerY = position.height / 2;
            
            const deltaX = x - centerX;
            const deltaY = y - centerY;
            
            // Stronger pull for magnetic feel
            magnet.style.transform = `translate(${deltaX * 0.4}px, ${deltaY * 0.4}px) scale(1.05)`;
            magnet.style.transition = 'transform 0.1s ease-out';
        });

        magnet.addEventListener('mouseleave', () => {
            magnet.style.transform = 'translate(0px, 0px) scale(1)';
            magnet.style.transition = 'transform 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275)';
        });
    });

    // 2. Parallax Effect for Hero Visual
    const heroVisual = document.querySelector('.photo-glow');
    if (heroVisual) {
        document.addEventListener('mousemove', (e) => {
            const moveX = (e.pageX - window.innerWidth / 2) * 0.01;
            const moveY = (e.pageY - window.innerHeight / 2) * 0.01;
            heroVisual.style.transform = `rotate(5deg) translate(${moveX}px, ${moveY}px)`;
        });
    }

    // 3. Scroll Reveal (Intersection Observer)
    const observerOptions = {
        threshold: 0.1
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, observerOptions);

    const revealElements = document.querySelectorAll('.project-card, .hero-text, .hero-visual, #about p');
    revealElements.forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(40px)';
        el.style.transition = 'all 1s cubic-bezier(0.2, 1, 0.3, 1)';
        observer.observe(el);
    });

    // 4. Project Card Mouse Glow
    const cards = document.querySelectorAll('.project-card');
    cards.forEach(card => {
        card.addEventListener('mousemove', (e) => {
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            card.style.setProperty('--x', `${x}px`);
            card.style.setProperty('--y', `${y}px`);
        });
    });

    // 5. Smooth Anchor Scrolling
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                window.scrollTo({
                    top: target.offsetTop - 100,
                    behavior: 'smooth'
                });
            }
        });
    });
});
