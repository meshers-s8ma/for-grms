// app/static/js/main.js

document.addEventListener('DOMContentLoaded', function() {

    // --- НАЧАЛО: НОВЫЙ БЛОК ДЛЯ WEBSOCKET УВЕДОМЛЕНИЙ ---

    /**
     * Создает и отображает всплывающее "тост"-уведомление.
     * @param {string} message - Текст сообщения для отображения.
     * @param {string} type - Тип уведомления ('success', 'info', 'error'), влияет на цвет и иконку.
     */
    function createToast(message, type = 'info') {
        // Находим или создаем контейнер для всех уведомлений
        let toastContainer = document.getElementById('toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.id = 'toast-container';
            // Стили Tailwind CSS для позиционирования контейнера
            toastContainer.className = 'fixed top-5 right-5 z-50 space-y-3';
            document.body.appendChild(toastContainer);
        }

        const toast = document.createElement('div');
        
        // Настройка иконок и цветов в зависимости от типа уведомления
        const icons = {
            info: '<svg class="w-6 h-6 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>',
            success: '<svg class="w-6 h-6 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>',
        };
        const colors = {
            info: 'bg-blue-50 border-blue-400',
            success: 'bg-green-50 border-green-400',
        };
        
        toast.className = `max-w-sm w-full shadow-lg rounded-lg pointer-events-auto ring-1 ring-black ring-opacity-5 overflow-hidden transform transition-all duration-300 ease-in-out ${colors[type] || colors['info']}`;
        
        toast.innerHTML = `
            <div class="p-4">
                <div class="flex items-start">
                    <div class="flex-shrink-0">
                        ${icons[type] || icons['info']}
                    </div>
                    <div class="ml-3 w-0 flex-1 pt-0.5">
                        <p class="text-sm font-medium text-gray-900">${message}</p>
                    </div>
                    <div class="ml-4 flex-shrink-0 flex">
                        <button class="inline-flex text-gray-400 hover:text-gray-500" onclick="this.closest('.toast-item').remove()">
                            <span class="sr-only">Close</span>
                            <svg class="h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" /></svg>
                        </button>
                    </div>
                </div>
            </div>
        `;
        toast.classList.add('toast-item');

        // Добавляем уведомление на страницу
        toastContainer.appendChild(toast);
        
        // Устанавливаем таймер на удаление уведомления
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(-20px)';
            setTimeout(() => toast.remove(), 300); // Удаляем после завершения анимации
        }, 5000); // 5 секунд
    }

    // Инициализируем соединение с сервером
    const socket = io();

    // Слушаем событие 'connect' для отладки
    socket.on('connect', function() {
        console.log('WebSocket connected!');
    });

    // Слушаем кастомное событие 'notification' от сервера
    socket.on('notification', function(data) {
        console.log('Received notification:', data.message);
        // Используем 'success' для событий, связанных с действиями, и 'info' для остальных
        const type = data.event.includes('completed') || data.event.includes('created') ? 'success' : 'info';
        createToast(data.message, type);
    });

    // --- КОНЕЦ НОВОГО БЛОКА ---


    // --- Логика для подтверждений через SweetAlert2 (без изменений) ---
    const confirmForms = document.querySelectorAll('.form-confirm');
    
    confirmForms.forEach(form => {
        form.addEventListener('submit', function(event) {
            event.preventDefault();
            const confirmText = this.dataset.text || 'Это действие необратимо!';
            
            Swal.fire({
                title: 'Вы уверены?',
                text: confirmText,
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#d33',
                cancelButtonColor: '#3085d6',
                confirmButtonText: 'Да, я уверен!',
                cancelButtonText: 'Отмена'
            }).then((result) => {
                if (result.isConfirmed) {
                    const submitButton = form.querySelector('button[type="submit"], input[type="submit"]');
                    if (submitButton) {
                        submitButton.classList.add('is-loading'); // Класс для индикации загрузки
                    }
                    form.submit();
                }
            });
        });
    });

    // --- Логика для индикации загрузки на ОБЫЧНЫХ формах (без изменений) ---
    const allOtherForms = document.querySelectorAll('form:not(.form-confirm)');
    
    allOtherForms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const submitButton = form.querySelector('button[type="submit"], input[type="submit"]');
            if (submitButton) {
                submitButton.classList.add('is-loading');
            }
        });
    });

    // Обработчик для решения проблемы с кэшем браузера (кнопка "Назад") (без изменений)
    window.addEventListener('pageshow', function (event) {
        if (event.persisted) {
            const loadingButtons = document.querySelectorAll('.is-loading');
            loadingButtons.forEach(function(button) {
                button.classList.remove('is-loading');
                button.disabled = false;
            });
        }
    });
});