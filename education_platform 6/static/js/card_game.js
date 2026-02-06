// ============================================
// JAVASCRIPT ДЛЯ ИГРЫ В КАРТОЧКИ
// ============================================

// Утилиты для карточек
const CardGame = {
    // Показать уведомление
    showNotification(message, type = 'info') {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show position-fixed top-0 start-50 translate-middle-x mt-3`;
        alertDiv.style.zIndex = '9999';
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        document.body.appendChild(alertDiv);
        
        // Автоматически закрыть через 5 секунд
        setTimeout(() => {
            alertDiv.remove();
        }, 5000);
    },

    // Валидация ответа
    validateAnswer(answerText) {
        if (!answerText || answerText.trim().length === 0) {
            this.showNotification('Ответ не может быть пустым!', 'danger');
            return false;
        }
        if (answerText.length < 5) {
            this.showNotification('Ответ слишком короткий (минимум 5 символов)', 'warning');
            return false;
        }
        return true;
    },

    // Валидация оценки
    validateRating(rating, isCorrect) {
        if (!rating) {
            this.showNotification('Выберите оценку!', 'danger');
            return false;
        }
        if (isCorrect === null) {
            this.showNotification('Укажите правильность ответа!', 'danger');
            return false;
        }
        return true;
    },

    // Форматирование даты
    formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString('ru-RU', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    },

    // Анимация элементов при загрузке
    animateElements() {
        const elements = document.querySelectorAll('.fade-in-up');
        elements.forEach((el, index) => {
            el.style.animationDelay = `${index * 0.1}s`;
        });
    },

    // Инициализация рейтинга звездочек
    initStarRating() {
        const starRatings = document.querySelectorAll('.star-rating');
        starRatings.forEach(rating => {
            const stars = rating.querySelectorAll('i');
            stars.forEach((star, index) => {
                star.addEventListener('click', () => {
                    stars.forEach((s, i) => {
                        if (i <= index) {
                            s.classList.remove('far');
                            s.classList.add('fas');
                        } else {
                            s.classList.remove('fas');
                            s.classList.add('far');
                        }
                    });
                });
            });
        });
    },

    // Показать/скрыть загрузку
    showLoading(show = true) {
        const loader = document.getElementById('gameLoader');
        if (loader) {
            if (show) {
                loader.style.display = 'flex';
            } else {
                loader.style.display = 'none';
            }
        }
    },

    // Подсчет статистики
    calculateStats(cards, answers) {
        const stats = {
            totalCards: cards.length,
            answeredCards: answers.length,
            correctAnswers: answers.filter(a => a.is_correct).length,
            incorrectAnswers: answers.filter(a => !a.is_correct).length,
            averageRating: 0
        };
        
        if (answers.length > 0) {
            const totalRating = answers.reduce((sum, a) => sum + (a.rating || 0), 0);
            stats.averageRating = (totalRating / answers.length).toFixed(1);
        }
        
        return stats;
    },

    // Обновить прогресс игры
    updateProgress(answered, total) {
        const progress = document.getElementById('gameProgress');
        if (progress) {
            const percentage = (answered / total) * 100;
            progress.style.width = percentage + '%';
            progress.textContent = `${answered} / ${total}`;
        }
    }
};

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // Анимация элементов
    CardGame.animateElements();

    // Инициализация рейтинга
    CardGame.initStarRating();

    // Добавить обработчик для кнопок
    document.querySelectorAll('.action-btn').forEach(btn => {
        btn.addEventListener('mouseenter', function() {
            this.style.transform = 'scale(1.05)';
        });
        btn.addEventListener('mouseleave', function() {
            this.style.transform = 'scale(1)';
        });
    });
});

// Экспорт для использования в шаблонах
window.CardGame = CardGame;
