

// app/static/js/dashboard.js

document.addEventListener('DOMContentLoaded', function() {
    // Кэш для хранения уже загруженных данных о деталях
    const detailsCache = {};
    
    // Основные элементы DOM, с которыми будем работать
    const mainTable = document.getElementById('main-dashboard-table');
    const bulkActionsBar = document.getElementById('bulk-actions-bar');
    const bulkActionsCounter = document.getElementById('bulk-actions-counter');
    const bulkClearButton = document.getElementById('bulk-clear-selection');
    const bulkDeleteForm = document.getElementById('bulk-delete-form');
    const bulkPrintForm = document.getElementById('bulk-print-form');
    const searchInput = document.getElementById('searchInput');

    function updateBulkActionsPanel() {
        if (!mainTable || !bulkActionsBar || !bulkActionsCounter) return;

        const selectedCheckboxes = mainTable.querySelectorAll('.part-checkbox:checked');
        const count = selectedCheckboxes.length;

        bulkActionsCounter.textContent = `Выбрано: ${count}`;
        if (count > 0) {
            bulkActionsBar.classList.remove('translate-y-full');
        } else {
            bulkActionsBar.classList.add('translate-y-full');
        }
    }

    function prepareFormForSubmit(form) {
        form.querySelectorAll('input[name="part_ids"]').forEach(input => input.remove());
        
        const selectedCheckboxes = mainTable.querySelectorAll('.part-checkbox:checked');
        selectedCheckboxes.forEach(cb => {
            const hiddenInput = document.createElement('input');
            hiddenInput.type = 'hidden';
            hiddenInput.name = 'part_ids';
            hiddenInput.value = cb.value;
            form.appendChild(hiddenInput);
        });
        return selectedCheckboxes.length;
    }

    if (bulkDeleteForm) {
        bulkDeleteForm.addEventListener('submit', function(event) {
            event.preventDefault();
            const selectedCount = prepareFormForSubmit(bulkDeleteForm);
            if (selectedCount === 0) {
                Swal.fire('Нет выбранных элементов', 'Пожалуйста, выберите хотя бы одну деталь.', 'info');
                return;
            }
            Swal.fire({
                title: 'Вы уверены?',
                text: `Вы собираетесь удалить ${selectedCount} деталей. Это действие необратимо!`,
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#d33',
                cancelButtonColor: '#3085d6',
                confirmButtonText: 'Да, удалить!',
                cancelButtonText: 'Отмена'
            }).then((result) => {
                if (result.isConfirmed) {
                    bulkDeleteForm.submit();
                }
            });
        });
    }

    if (bulkPrintForm) {
        bulkPrintForm.addEventListener('submit', function(event) {
            if (prepareFormForSubmit(bulkPrintForm) === 0) {
                event.preventDefault();
                Swal.fire('Нет выбранных элементов', 'Пожалуйста, выберите хотя бы одну деталь для печати.', 'info');
            }
        });
    }

    if (bulkClearButton) {
        bulkClearButton.addEventListener('click', () => {
            mainTable.querySelectorAll('.part-checkbox:checked, .select-all-parts:checked').forEach(cb => cb.checked = false);
            updateBulkActionsPanel();
        });
    }

    if (mainTable) {
        mainTable.addEventListener('click', async function(event) {
            const productToggle = event.target.closest('.product-toggle');
            
            if (productToggle) {
                const productRow = productToggle.closest('.product-row');
                const productDesignation = productRow.dataset.productDesignation;
                const safeKey = productRow.dataset.safeKey;
                const detailsRow = document.getElementById(`details-for-${safeKey}`);
                const contentCell = detailsRow.querySelector('.details-placeholder');
                const isVisible = !detailsRow.classList.contains('hidden');

                detailsRow.classList.toggle('hidden');
                productToggle.innerHTML = isVisible ? `${productDesignation} ▾` : `${productDesignation} ▴`;

                if (!isVisible && detailsCache[productDesignation]) {
                    contentCell.innerHTML = detailsCache[productDesignation];
                    return;
                }

                contentCell.innerHTML = `<div class="p-8 text-center text-gray-500">Загрузка...</div>`;
                
                try {
                    const response = await fetch(`/api/parts/${encodeURIComponent(productDesignation)}`);
                    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                    
                    const data = await response.json();
                    const { parts, permissions } = data;
                    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

                    if (parts.length === 0) {
                        contentCell.innerHTML = '<div class="p-8 text-center text-gray-500">Детали не найдены.</div>';
                    } else {
                        // --- НАЧАЛО ИЗМЕНЕНИЯ: Полностью переписанный блок генерации HTML ---
                        const rowsHtml = parts.map(part => {
                            const progress = (part.quantity_completed / part.quantity_total) * 100;
                            const progressText = `${part.quantity_completed} из ${part.quantity_total}`;
                            
                            const routeHtml = part.route_stages.map(stage => {
                                let classes = 'text-gray-500'; // pending
                                let title = `Ожидание (${stage.qty_done}/${part.quantity_total})`;
                                if (stage.status === 'completed') {
                                    classes = 'text-green-500 line-through';
                                    title = `Выполнено (${stage.qty_done}/${part.quantity_total})`;
                                } else if (stage.status === 'in_progress') {
                                    classes = 'text-blue-600 font-bold';
                                    title = `В процессе (${stage.qty_done}/${part.quantity_total})`;
                                }
                                return `<span class="${classes}" title="${title}">${stage.name}</span>`;
                            }).join(' <span class="text-gray-300">→</span> ') || '<span class="text-gray-400 italic">Маршрут не назначен</span>';

                            const deleteBtn = permissions?.can_delete ? `<form action="${part.delete_url}" method="post" class="inline form-confirm" data-text="Удалить деталь ${part.part_id}?"><input type="hidden" name="csrf_token" value="${csrfToken}"><button type="submit" class="text-red-600 hover:text-red-900" title="Удалить">✖</button></form>` : '';
                            const editBtn = permissions?.can_edit ? `<a href="${part.edit_url}" class="text-blue-600 hover:text-blue-900" title="Редактировать">✎</a>` : '';
                            const qrBtn = permissions?.can_generate_qr ? `<form action="${part.qr_url}" method="post" class="inline"><input type="hidden" name="csrf_token" value="${csrfToken}"><button type="submit" class="text-green-600 hover:text-green-900" title="Скачать QR-код"></button></form>` : '';
                            
                            const progressBarHtml = `
                                <div class="w-full bg-gray-200 rounded-full h-2.5">
                                    <div class="bg-blue-600 h-2.5 rounded-full" style="width: ${progress}%"></div>
                                </div>
                                <small>${progressText}</small>
                            `;

                            return `
                                <tr class="hover:bg-gray-100">
                                    <td class="px-6 py-4"><input type="checkbox" value="${part.part_id}" class="part-checkbox rounded border-gray-300"></td>
                                    <td class="px-6 py-4"><a href="${part.history_url}" class="text-blue-600 hover:underline font-medium">${part.part_id}</a></td>
                                    <td class="px-6 py-4 text-sm text-gray-900">${part.name}</td>
                                    <td class="px-6 py-4 text-sm text-gray-500">${part.material}</td>
                                    <td class="px-6 py-4 text-xs">${routeHtml}</td>
                                    <td class="px-6 py-4">${progressBarHtml}</td>
                                    <td class="px-6 py-4 text-sm text-gray-500">${part.responsible_user}</td>
                                    <td class="px-6 py-4 text-right text-sm font-medium space-x-4">${editBtn} ${qrBtn} ${deleteBtn}</td>
                                </tr>`;
                        }).join('');
                        
                        contentCell.innerHTML = `
                            <table class="min-w-full details-table">
                                <thead class="bg-gray-100">
                                    <tr>
                                        <th class="px-6 py-3 w-12"><input type="checkbox" class="select-all-parts rounded border-gray-300" title="Выбрать все"></th>
                                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Обозначение</th>
                                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Наименование</th>
                                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Материал</th>
                                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Маршрут</th>
                                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Прогресс (шт.)</th>
                                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Ответственный</th>
                                        <th class="px-6 py-3"></th>
                                    </tr>
                                </thead>
                                <tbody class="bg-white divide-y divide-gray-200">${rowsHtml}</tbody>
                            </table>`;
                         // --- КОНЕЦ ИЗМЕНЕНИЯ ---
                    }
                    detailsCache[productDesignation] = contentCell.innerHTML;
                } catch (error) {
                    console.error('Ошибка загрузки деталей:', error);
                    contentCell.innerHTML = '<div class="p-8 text-center text-red-500">Ошибка загрузки. Попробуйте обновить страницу.</div>';
                }
            }
        });

        mainTable.addEventListener('change', function(event) {
            if (event.target.matches('.part-checkbox, .select-all-parts')) {
                if (event.target.matches('.select-all-parts')) {
                    const isChecked = event.target.checked;
                    event.target.closest('.details-table')?.querySelectorAll('.part-checkbox').forEach(cb => cb.checked = isChecked);
                }
                updateBulkActionsPanel();
            }
        });
    }

    if (searchInput) {
        searchInput.addEventListener('keyup', function() {
            const filter = searchInput.value.toUpperCase();
            document.querySelectorAll('#main-dashboard-table > tbody > .product-row').forEach(row => {
                const txtValue = row.dataset.productDesignation || '';
                row.style.display = txtValue.toUpperCase().indexOf(filter) > -1 ? "" : "none";
            });
        });
    }
});